package com.example.cdk;

import java.nio.file.Path;
import software.amazon.awscdk.CfnOutput;
import software.amazon.awscdk.Duration;
import software.amazon.awscdk.RemovalPolicy;
import software.amazon.awscdk.Stack;
import software.amazon.awscdk.StackProps;
import software.amazon.awscdk.services.apigateway.LambdaIntegration;
import software.amazon.awscdk.services.apigateway.RestApi;
import software.amazon.awscdk.services.apigateway.StageOptions;
import software.amazon.awscdk.services.lambda.Code;
import software.amazon.awscdk.services.lambda.Function;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.logs.LogGroup;
import software.amazon.awscdk.services.logs.RetentionDays;
import software.constructs.Construct;

/**
 * The application infrastructure: API Gateway -> Lambda (Java 21), plus its logs.
 *
 * <p>This is deliberately minimal. It has no API authorization, WAF, alarms or
 * custom domain, which a production API would need before going live.
 */
public class GreetingApiStack extends Stack {

    public GreetingApiStack(Construct scope, String id, String stage, Path lambdaJar) {
        super(scope, id, StackProps.builder()
                .description("Greeting API (" + stage + ") from aws-cdk-path-to-production")
                // Production cannot be deleted by accident with `cdk destroy`.
                .terminationProtection("prod".equals(stage))
                .build());

        boolean production = "prod".equals(stage);

        // Bounded log retention; keep production logs if the stack is ever removed.
        LogGroup logs = LogGroup.Builder.create(this, "HelloLambdaLogs")
                .retention(RetentionDays.ONE_MONTH)
                .removalPolicy(production ? RemovalPolicy.RETAIN : RemovalPolicy.DESTROY)
                .build();

        // The JAR was built once by app CI and fetched by version + SHA-256.
        Function hello = Function.Builder.create(this, "HelloLambda")
                .runtime(Runtime.JAVA_21)
                .handler("com.example.hello.HelloHandler::handleRequest")
                .code(Code.fromAsset(lambdaJar.toString()))
                .memorySize(512)
                .timeout(Duration.seconds(10))
                .logGroup(logs)
                .build();

        RestApi api = RestApi.Builder.create(this, "GreetingApi")
                .restApiName("greeting-api-" + stage)
                // Name the API stage after the environment (the CDK default is "prod").
                .deployOptions(StageOptions.builder().stageName(stage).build())
                // Don't manage the account-wide API Gateway logging role from an app stack.
                .cloudWatchRole(false)
                .build();

        api.getRoot()
                .addResource("hello")
                .addMethod("GET", new LambdaIntegration(hello));

        CfnOutput.Builder.create(this, "ApiUrl")
                .description("Public URL of GET /hello, used by the smoke test")
                .value(api.urlForPath("/hello"))
                .build();
    }
}
