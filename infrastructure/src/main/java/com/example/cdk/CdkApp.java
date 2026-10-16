package com.example.cdk;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import software.amazon.awscdk.App;
import software.amazon.awscdk.Tags;

/**
 * Entry point that the CDK CLI runs (see cdk.json).
 *
 * <p>One stack definition, three environments. {@code DEPLOY_ENV} selects which
 * one to synthesize; the AWS account and region come from the credentials of
 * whoever runs {@code cdk deploy}, so each environment's workflow job must use
 * that environment's own AWS identity.
 */
public final class CdkApp {

    static final List<String> STAGES = List.of("dev", "qa", "prod");

    static final Map<String, String> STACK_NAMES = Map.of(
            "dev", "GreetingApiDevStack",
            "qa", "GreetingApiQaStack",
            "prod", "GreetingApiProdStack");

    private CdkApp() {
    }

    public static void main(String[] args) {
        String stage = System.getenv().getOrDefault("DEPLOY_ENV", "dev");
        if (!STAGES.contains(stage)) {
            throw new IllegalArgumentException(
                    "DEPLOY_ENV must be one of " + STAGES + " but was '" + stage + "'");
        }

        Path lambdaJar = Path.of(
                System.getenv().getOrDefault("LAMBDA_JAR", "artifacts/hello-world-lambda.jar"));
        if (!Files.isRegularFile(lambdaJar)) {
            throw new IllegalStateException("Lambda JAR not found at " + lambdaJar.toAbsolutePath()
                    + ". Fetch the released artifact first (scripts/fetch-lambda-artifact.sh),"
                    + " or copy a local app build there for a synth-only check.");
        }

        App app = new App();
        new GreetingApiStack(app, STACK_NAMES.get(stage), stage, lambdaJar);

        Tags.of(app).add("project", "aws-cdk-path-to-production");
        Tags.of(app).add("stage", stage);

        app.synth();
    }
}
