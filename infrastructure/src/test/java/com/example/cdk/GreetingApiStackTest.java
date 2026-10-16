package com.example.cdk;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import software.amazon.awscdk.App;
import software.amazon.awscdk.assertions.Template;

/**
 * Infrastructure has unit tests too. These synthesize the stack in memory and
 * assert on the CloudFormation it produces. Nothing touches AWS.
 */
class GreetingApiStackTest {

    @TempDir
    static Path tempDir;

    private static Path lambdaJar;

    @BeforeAll
    static void createPlaceholderJar() throws IOException {
        // The stack only needs a file to package; its contents don't matter here.
        lambdaJar = tempDir.resolve("hello-world-lambda.jar");
        try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(lambdaJar))) {
            zip.putNextEntry(new ZipEntry("placeholder.txt"));
            zip.write("test".getBytes(StandardCharsets.UTF_8));
            zip.closeEntry();
        }
    }

    private static GreetingApiStack stack(String stage) {
        return new GreetingApiStack(new App(), "TestStack-" + stage, stage, lambdaJar);
    }

    private static Template template(String stage) {
        return Template.fromStack(stack(stage));
    }

    @Test
    void deploysAJava21LambdaWithTheExpectedHandler() {
        template("dev").hasResourceProperties("AWS::Lambda::Function", Map.of(
                "Runtime", "java21",
                "Handler", "com.example.hello.HelloHandler::handleRequest",
                "MemorySize", 512,
                "Timeout", 10));
    }

    @Test
    void exposesGetHello() {
        Template template = template("dev");
        template.hasResourceProperties("AWS::ApiGateway::Resource", Map.of("PathPart", "hello"));
        template.hasResourceProperties("AWS::ApiGateway::Method", Map.of("HttpMethod", "GET"));
        template.hasOutput("ApiUrl", Map.of());
    }

    @Test
    void namesTheApiStageAfterTheEnvironment() {
        template("qa").hasResourceProperties("AWS::ApiGateway::Stage", Map.of("StageName", "qa"));
    }

    @Test
    void leavesAccountWideApiGatewaySettingsAlone() {
        template("dev").resourceCountIs("AWS::ApiGateway::Account", 0);
    }

    @Test
    void boundsLogRetention() {
        template("dev").hasResourceProperties("AWS::Logs::LogGroup", Map.of("RetentionInDays", 30));
    }

    @Test
    void protectsOnlyProductionFromDeletion() {
        assertTrue(stack("prod").getTerminationProtection());
        assertFalse(stack("dev").getTerminationProtection());
        assertFalse(stack("qa").getTerminationProtection());
    }
}
