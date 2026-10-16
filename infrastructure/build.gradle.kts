// The infrastructure: an AWS CDK app written in Java.
// It never compiles the application. It deploys a released, pinned JAR
// that a workflow places in infrastructure/artifacts/ before synthesis.

plugins {
    application
}

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencies {
    implementation("software.amazon.awscdk:aws-cdk-lib:2.273.0")
    implementation("software.constructs:constructs:10.8.1")

    testImplementation(platform("org.junit:junit-bom:6.1.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

application {
    // cdk.json runs this entry point via `./gradlew --quiet run`.
    mainClass = "com.example.cdk.CdkApp"
}

tasks.test {
    // CDK for Java runs on the jsii runtime, so Node.js must be on the PATH.
    useJUnitPlatform()
}
