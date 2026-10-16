#!/usr/bin/env bash
# Post-deployment smoke test with bounded retries.
#
# `cdk deploy` has already waited for CloudFormation to finish. The retries only
# cover the short window before a freshly deployed API answers, so there is no
# fixed sleep up front. A failure fails the job; it does NOT roll back the
# deployment that CloudFormation already completed.
#
# Usage: scripts/smoke-test.sh <url> [expected-body]
set -euo pipefail

url="${1:?usage: smoke-test.sh <url> [expected-body]}"
expected="${2:-Hello, World!}"
attempts="${SMOKE_ATTEMPTS:-10}"
delay="${SMOKE_DELAY_SECONDS:-3}"

body="$(mktemp)"
trap 'rm -f "$body"' EXIT

for attempt in $(seq 1 "$attempts"); do
  code="$(curl --silent --show-error --max-time 10 --output "$body" --write-out '%{http_code}' "$url" || true)"
  if [[ "$code" == "200" && "$(cat "$body")" == "$expected" ]]; then
    echo "Smoke test passed on attempt $attempt: HTTP 200 and the expected body"
    exit 0
  fi
  echo "Attempt $attempt/$attempts: HTTP ${code:-000}"
  if [[ "$attempt" -lt "$attempts" ]]; then sleep "$delay"; fi
done

echo "::error::Smoke test failed after $attempts attempts against $url" >&2
echo "The deployment itself is not rolled back. Follow the rollback steps in docs/06-release-promotion.md." >&2
exit 1
