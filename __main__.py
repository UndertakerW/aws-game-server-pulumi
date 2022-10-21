"""An AWS Python Pulumi program"""

import json
import re
import pulumi
import pulumi_aws as aws

lambdaFunctionKeys = [
    "game-messaging",
    "join-game",
    "disconnect-game",
]

websocketApiRouteKeys = [
    "OnMessage",
    "$connect",
    "$disconnect",
    "$default",
]

websocketApiIntegrationKeys = [
    "OnMessageIntegration",
    "JoinGameIntegration",
    "DisconnectGameIntegration",
    "DefaultIntegration",
]

websocketApiRoutes = []
lambdaFunctionCode = []
lambdaFunctions = []
lambdaPermissions = []
apiRoutes = []
apiIntegrations = []

tags = {
    "Environment": pulumi.get_stack(),
    "ProjectName": pulumi.get_project(),
    "StackName": pulumi.get_stack(),
    "Team": "WeiWu",
}

# DynamoDB item table
dbTable = aws.dynamodb.Table(
    "game-session-2022-pulumi",
    attributes=[aws.dynamodb.TableAttributeArgs(name="uuid", type="S")],
    hash_key="uuid",
    read_capacity=1,
    write_capacity=1,
    tags=tags,
)

dbTableIAmPolicy = aws.iam.Policy(
    "iam-policy-2022-pulumi",
    description="This policy grants permission to interact with DynamoDB",
    policy=dbTable.arn.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:DeleteItem",
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:Scan",
                            "dynamodb:UpdateItem",
                        ],
                        "Resource": arn,
                    }
                ],
            }
        )
    ),
    tags=tags,
)

# Create Lambda Function role
dbTableIAmRole = aws.iam.Role(
    "iam-role-2022-pulumi",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Sid": "",
                    "Principal": {
                        "Service": "lambda.amazonaws.com",
                    },
                },
            ],
        }
    ),
    managed_policy_arns=[
        "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        dbTableIAmPolicy.arn,
    ],
    tags=tags,
)

# Get Lambda Code
for i in range(len(lambdaFunctionKeys)):
    lambdaFunctionCode += pulumi.asset.AssetArchive(
        {
            ".": pulumi.asset.FileArchive("./src/lambda/" + lambdaFunctionKeys[i]),
        }
    )

# Creating API Gateway WebSocket API
gameWebsocketApi = aws.apigatewayv2.Api(
    "game-websocket-api-2022-pulumi",
    protocol_type="WEBSOCKET",
    description="API Gateway Websocket API",
    tags=tags,
)

# Create Lambda Function
for i in range(len(lambdaFunctionKeys)):
    lambdaFunctions += aws.lambda_.Function(
        lambdaFunctionKeys[i] + "-2022-pulumi",
        role=dbTableIAmRole.arn,
        handler="index.handler",
        runtime=aws.lambda_.Runtime.NODE_JS14D_X,
        code=lambdaFunctionCode[i],
        tags=tags,
        environment=aws.lambda_.FunctionEnvironmentArgs(
            variables={"DYNAMODB_TABLE": dbTable.name}
        ),
    )
    lambdaPermissions += aws.lambda_.Permission(
        lambdaFunctionKeys[i] + "Permissions" + "-2022-pulumi",
        action="lambda:InvokeFunction",
        principal="apigateway.amazonaws.com",
        function=lambdaFunctions[i].arn,
        source_arn=pulumi.Output.concat(gameWebsocketApi.execution_arn, "/*/*"),
        opts=pulumi.ResourceOptions(depends_on=[gameWebsocketApi, lambdaFunctions[i]]),
    )


gameWebsocketApiRouteGameMessaging = aws.apigatewayv2.Route(
    "OnMessage",
    api_id=gameWebsocketApi.id,
    route_key="OnMessage")

gameWebsocketApiRouteDefault = aws.apigatewayv2.Route(
    "default",
    api_id=gameWebsocketApi.id,
    route_key="$default")

gameWebsocketApiRouteJoinGame = aws.apigatewayv2.Route(
    "connect",
    api_id=gameWebsocketApi.id,
    route_key="$connect")

gameWebsocketApiRouteDisconnectGame = aws.apigatewayv2.Route(
    "disconnect",
    api_id=gameWebsocketApi.id,
    route_key="$disconnect")


# Permissions to API Gateway to invoke the lambda function
lambdaPermission = aws.lambda_.Permission(
    "dynamoDbCrudLambdaPermissions",
    action="lambda:InvokeFunction",
    principal="apigateway.amazonaws.com",
    function=lambdaFunctionGameMessaging.arn,
    source_arn=pulumi.Output.concat(gameWebsocketApi.execution_arn, "/*/*"),
    opts=pulumi.ResourceOptions(depends_on=[gameWebsocketApi, lambdaFunctionGameMessaging]),
)

for i in range(len(websocketApiIntegrationKeys)):
    apiIntegrations += aws.apigatewayv2.Integration(
    websocketApiIntegrationKeys[i] + "-2022-pulumi",
    api_id=gameWebsocketApi.id,
    integration_type="AWS_PROXY",
    connection_type="INTERNET",
    content_handling_strategy="CONVERT_TO_TEXT",
    description="Integration for game-messaging lambda function",
    integration_method="POST",
    integration_uri=lambdaFunctions[i%len(lambdaFunctions)].invoke_arn,
    passthrough_behavior="WHEN_NO_MATCH"
)

# Creating routes
for i in range(len(websocketApiRouteKeys)):
    websocketApiRoutes.append(
        aws.apigatewayv2.Route(
            websocketApiRouteKeys[i] + "-2022-pulumi",
            api_id=gameWebsocketApi.id,
            route_key=websocketApiRouteKeys[i],
            target=pulumi.Output.concat(
                "integrations/", websocketApiIntegrationKeys[i].id
            ),
        )
    )


# Creating default stage
publicHttpApiDefaultStage = aws.apigatewayv2.Stage(
    "publicHttpApiDefaultStage",
    api_id=gameWebsocketApi.id,
    name=pulumi.get_stack(),
    auto_deploy=True,
    tags=tags,
    opts=pulumi.ResourceOptions(depends_on=websocketApiRoutes),
)

# Outputs
pulumi.export(name="dynamoDbCrudLambda", value=lambdaFunctionGameMessaging.name)
pulumi.export(
    name="publicHttpApiDefaultStage", value=publicHttpApiDefaultStage.invoke_url
