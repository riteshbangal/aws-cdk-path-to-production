#!/usr/bin/env bash
# Downloads the released Lambda JAR pinned in infrastructure/lambda-artifact.env
# and verifies its SHA-256. The JAR lands in infrastructure/artifacts/, which is
# the only place the CDK app reads it from.
#
# Required: ARTIFACTORY_BASE_URL  repository root, e.g. https://acme.jfrog.io/artifactory/lambda-release-local
#           ARTIFACTORY_TOKEN     read-only token
# Optional: REQUIRE_PINNED_DIGEST=true  fail if LAMBDA_SHA256 is empty (set by deployments)
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pin_file="$repo_root/infrastructure/lambda-artifact.env"
target="$repo_root/infrastructure/artifacts/hello-world-lambda.jar"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

# shellcheck source=/dev/null
source "$pin_file"
: "${LAMBDA_VERSION:?LAMBDA_VERSION is not set in infrastructure/lambda-artifact.env}"
: "${ARTIFACTORY_BASE_URL:?Set ARTIFACTORY_BASE_URL to the artifact repository root URL}"
: "${ARTIFACTORY_TOKEN:?Set ARTIFACTORY_TOKEN to a read-only token}"

if [[ -z "${LAMBDA_SHA256:-}" && "${REQUIRE_PINNED_DIGEST:-false}" == "true" ]]; then
  echo "::error::LAMBDA_SHA256 is empty in infrastructure/lambda-artifact.env. Deployments only use a digest-pinned release." >&2
  exit 1
fi

url="${ARTIFACTORY_BASE_URL%/}/hello-world-lambda/${LAMBDA_VERSION}/hello-world-lambda.jar"
mkdir -p "$(dirname "$target")"
echo "Fetching hello-world-lambda ${LAMBDA_VERSION}"
curl --fail --location --silent --show-error \
  -H "Authorization: Bearer ${ARTIFACTORY_TOKEN}" \
  -o "$target" "$url"

actual="$(sha256 "$target")"
if [[ -n "${LAMBDA_SHA256:-}" ]]; then
  if [[ "$actual" != "$LAMBDA_SHA256" ]]; then
    rm -f "$target"
    echo "::error::SHA-256 mismatch for hello-world-lambda ${LAMBDA_VERSION}: pinned ${LAMBDA_SHA256}, downloaded ${actual}" >&2
    exit 1
  fi
  echo "Verified SHA-256 ${actual}"
else
  echo "::warning::LAMBDA_SHA256 is not pinned yet. The downloaded JAR has SHA-256 ${actual}."
fi
