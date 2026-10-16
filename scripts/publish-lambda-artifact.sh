#!/usr/bin/env bash
# Publishes the JAR that app CI just built and tested, exactly once per version.
#
# Required: VERSION               e.g. 1.2.3 (from the Git tag v1.2.3)
#           ARTIFACTORY_BASE_URL  repository root URL
#           ARTIFACTORY_TOKEN     token allowed to deploy (write) to that repository
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
jar="$repo_root/app/build/libs/hello-world-lambda.jar"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}

: "${VERSION:?VERSION is required, e.g. 1.2.3}"
: "${ARTIFACTORY_BASE_URL:?Configure the ARTIFACTORY_BASE_URL repository variable}"
: "${ARTIFACTORY_TOKEN:?Configure the ARTIFACTORY_PUBLISH_TOKEN repository secret}"
[[ -f "$jar" ]] || { echo "::error::$jar not found. Build the app first." >&2; exit 1; }

url="${ARTIFACTORY_BASE_URL%/}/hello-world-lambda/${VERSION}/hello-world-lambda.jar"
auth=(-H "Authorization: Bearer ${ARTIFACTORY_TOKEN}")

# Released versions are immutable. Never overwrite one; release a new version instead.
# (Also enforce this with the repository's own no-overwrite policy.)
status="$(curl --silent --head --output /dev/null --write-out '%{http_code}' "${auth[@]}" "$url" || true)"
if [[ "$status" == "200" ]]; then
  echo "::error::hello-world-lambda ${VERSION} already exists. Released versions are immutable." >&2
  exit 1
fi

digest="$(sha256 "$jar")"
# Artifactory verifies the upload against this checksum header.
curl --fail --silent --show-error "${auth[@]}" \
  -H "X-Checksum-Sha256: ${digest}" \
  --upload-file "$jar" "$url"

echo "Published hello-world-lambda ${VERSION} with SHA-256 ${digest}"

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  cat >> "$GITHUB_STEP_SUMMARY" <<EOF
### Released hello-world-lambda ${VERSION}

To deploy this release, pin it in \`infrastructure/lambda-artifact.env\` through a pull request:

\`\`\`
LAMBDA_VERSION=${VERSION}
LAMBDA_SHA256=${digest}
\`\`\`
EOF
fi
