# 04 · Implementation walkthrough: the files and the decisions

> The code is the reference. This page explains **why** each piece looks the way it does, so you can adapt the decisions rather than copy the files.

**Versions:** Java 21 · Gradle 9.8.1 (wrapper) · Shadow 9.6.1 · AWS CDK library 2.273.0, CLI 2.1145.0 · JUnit 6 · Node.js 24 · `eu-west-1` by default.

## Two independent builds

![Two kinds of code](diagrams/02-two-kinds-of-code.png)

`app/` and `infrastructure/` are separate Gradle builds, each with its own wrapper. The application team can upgrade its build without touching the infrastructure build, and the infrastructure never compiles the application. It only deploys a released JAR.

## `app/`: the payload

- [`HelloHandler.java`](../app/src/main/java/com/example/hello/HelloHandler.java) returns `Hello, World!` as `text/plain` through the API Gateway proxy integration.
- [`build.gradle.kts`](../app/build.gradle.kts) builds a fat JAR with Shadow, under one fixed name: `hello-world-lambda.jar`. The **version** comes from the Git tag (`-PreleaseVersion=1.2.3`) and is recorded in the JAR manifest and in the artifact repository path, `hello-world-lambda/1.2.3/hello-world-lambda.jar`.
- Gradle 9 needs `junit-platform-launcher` declared explicitly, which is why it appears in the dependencies.

## The release pin

[`infrastructure/lambda-artifact.env`](../infrastructure/lambda-artifact.env) is the contract between the two halves:

```bash
LAMBDA_VERSION=1.0.0
LAMBDA_SHA256=        # filled in from App CI's output when 1.0.0 is published
```

- Changing it is a pull request, so every promotion is reviewed and recorded in Git.
- [`fetch-lambda-artifact.sh`](../scripts/fetch-lambda-artifact.sh) downloads exactly that version and checks its SHA-256. Deployments refuse to run while the digest is empty.
- The JAR lands in `infrastructure/artifacts/` (ignored by Git), the only place the CDK app reads from. A local `app/build` output can't slip into a deployment by accident.

## `infrastructure/`: the CDK app

[`CdkApp.java`](../infrastructure/src/main/java/com/example/cdk/CdkApp.java) picks the environment from `DEPLOY_ENV` (`dev`, `qa`, `prod`) and fails early, with a clear message, if the JAR is missing. The account and region come from the deploying identity, so each environment's job must use that environment's role.

[`GreetingApiStack.java`](../infrastructure/src/main/java/com/example/cdk/GreetingApiStack.java) is small, but each line is a decision:

| Line | Why |
|---|---|
| `Runtime.JAVA_21`, 512 MB, 10 s timeout | Matches the build; generous enough for a Java cold start |
| Explicit `LogGroup`, 30-day retention | Logs don't pile up forever; prod logs are retained if the stack is deleted |
| `deployOptions(stageName(stage))` | The URL says `/dev/hello` in dev. CDK's default stage name is `prod` everywhere, which is confusing. |
| `cloudWatchRole(false)` | Don't let an app stack own the account-wide API Gateway logging role |
| `terminationProtection` on prod only | `cdk destroy` can't remove production by accident |
| `CfnOutput ApiUrl` | The smoke test reads the URL from the deploy output |

[`GreetingApiStackTest.java`](../infrastructure/src/test/java/com/example/cdk/GreetingApiStackTest.java) synthesizes the stack in memory and asserts on the generated CloudFormation: runtime, route, stage name, log retention, termination protection. Infrastructure gets unit tests like any other code.

`cdk.json` runs the app with `./gradlew --quiet run`, and CDK for Java needs Node.js on the PATH.

## The workflows

| File | What it does |
|---|---|
| [`actions/setup-toolchain`](../.github/actions/setup-toolchain/action.yml) | One place for tool versions: Java, Gradle, Node.js, CDK CLI, cfn-lint |
| [`app-ci.yml`](../.github/workflows/app-ci.yml) | Build, test, package. On a `v*.*.*` tag, publish **the same JAR it just tested**, and refuse to overwrite an existing version |
| [`infra-ci.yml`](../.github/workflows/infra-ci.yml) | CDK unit tests, then synth and `cfn-lint` for dev, qa and prod, plus a lint of the foundation template |
| [`release.yml`](../.github/workflows/release.yml) | Fetch the pinned JAR, synthesize **once**, then promote dev → qa → production |
| [`deploy-environment.yml`](../.github/workflows/deploy-environment.yml) | Reusable: OIDC sign-in, `cdk deploy --app cdk.out/<env>`, smoke test |
| [`show-oidc-claims.yml`](../.github/workflows/show-oidc-claims.yml) | Manual helper that prints the OIDC claims to match in the trust policy |

Two details worth copying:

- **Infra CI works without an artifact repository.** Forks, pull requests from forks (which get no secrets) and first-time readers have no Artifactory, so Infra CI builds the JAR from the same commit, purely so synthesis has a file to package, and says so in a notice. The release pipeline never takes this shortcut.
- **The release deploys pre-built assemblies.** `synthesize` writes `cdk.out/dev`, `cdk.out/qa` and `cdk.out/prod` once, and each deploy job runs `cdk deploy --app cdk.out/<env>`. Nothing is rebuilt or re-synthesized between environments, so prod gets exactly what dev and qa tested.

## The scripts

| Script | Used by |
|---|---|
| [`publish-lambda-artifact.sh`](../scripts/publish-lambda-artifact.sh) | App CI on tags: upload with a SHA-256 checksum header, never overwrite |
| [`fetch-lambda-artifact.sh`](../scripts/fetch-lambda-artifact.sh) | Infra CI and Release: download the pinned version, verify its digest |
| [`synth-assemblies.sh`](../scripts/synth-assemblies.sh) | Infra CI and Release: one assembly per environment, then `cfn-lint` (errors fail the run, warnings are shown) |
| [`smoke-test.sh`](../scripts/smoke-test.sh) | Every deploy: HTTP 200 **and** the exact body, with bounded retries |
| [`integration-test.sh`](../scripts/integration-test.sh) | The QA gate: content type, only `GET` exposed, unknown paths rejected |

## Configuration reference

| Where | Name | Purpose |
|---|---|---|
| Repository variable | `ARTIFACTORY_BASE_URL` | Root of the artifact repository, e.g. `https://acme.jfrog.io/artifactory/lambda-release-local` |
| Repository secret | `ARTIFACTORY_PUBLISH_TOKEN` | Write token, used only by App CI on tags |
| Repository secret | `ARTIFACTORY_READ_TOKEN` | Read-only token for Infra CI and Release |
| Repository variable | `DEPLOYMENTS_ENABLED` | `true` makes merges to `main` trigger the Release workflow |
| Environment variable (dev, qa, production) | `AWS_DEPLOY_ROLE_ARN` | Output of the foundation stack for that environment |
| Environment variable (optional) | `AWS_REGION` | Defaults to `eu-west-1` |
| Environment protection (production) | Required reviewers | The production approval gate |
