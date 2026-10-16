// The application: a deliberately tiny Java 21 Lambda.
// Its only job here is to be the payload that travels the delivery path.

plugins {
    java
    id("com.gradleup.shadow") version "9.6.1"
}

group = "com.example"
// Release builds pass -PreleaseVersion=1.2.3 (taken from the Git tag in app-ci.yml).
// Local and pull-request builds are snapshots and are never published.
version = providers.gradleProperty("releaseVersion").getOrElse("0.0.0-SNAPSHOT")

repositories {
    mavenCentral()
}

java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}

dependencies {
    implementation("com.amazonaws:aws-lambda-java-core:1.4.1")
    implementation("com.amazonaws:aws-lambda-java-events:3.16.1")

    testImplementation(platform("org.junit:junit-bom:6.1.3"))
    testImplementation("org.junit.jupiter:junit-jupiter")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
}

tasks.shadowJar {
    // One fixed file name; the version lives in the artifact repository path
    // (hello-world-lambda/<version>/hello-world-lambda.jar) and in the manifest.
    archiveFileName = "hello-world-lambda.jar"
    manifest {
        attributes("Implementation-Version" to project.version)
    }
}

tasks.build {
    dependsOn(tasks.shadowJar)
}
