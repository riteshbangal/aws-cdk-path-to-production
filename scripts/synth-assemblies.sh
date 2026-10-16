#!/usr/bin/env bash
# Synthesizes one cloud assembly (CloudFormation template + packaged assets)
# per environment and lints each template.
#
# Synthesis only writes files. It does not touch AWS, and a clean synth does
# not prove that a deployment will succeed.
#
# Usage:  scripts/synth-assemblies.sh [dev] [qa] [prod]    (default: all three)
# Output: infrastructure/cdk.out/<env>/
# Needs:  the Lambda JAR in infrastructure/artifacts/, the CDK CLI, cfn-lint.
#         Set CDK_CMD (e.g. "npx aws-cdk@2.1145.0") if `cdk` is not installed globally.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/infrastructure"

read -r -a cdk <<< "${CDK_CMD:-cdk}"
region="${AWS_REGION:-eu-west-1}"

if [[ $# -gt 0 ]]; then envs=("$@"); else envs=(dev qa prod); fi

for env in "${envs[@]}"; do
  case "$env" in
    dev)  stack=GreetingApiDevStack ;;
    qa)   stack=GreetingApiQaStack ;;
    prod) stack=GreetingApiProdStack ;;
    *)    echo "::error::Unknown environment '$env' (expected dev, qa or prod)" >&2; exit 1 ;;
  esac

  echo "::group::Synthesize $stack"
  DEPLOY_ENV="$env" "${cdk[@]}" synth --quiet --output "cdk.out/$env" "$stack"
  echo "::endgroup::"

  echo "Linting cdk.out/$env/$stack.template.json"
  cfn-lint --non-zero-exit-code error --regions "$region" "cdk.out/$env/$stack.template.json"
done
