#!/usr/bin/env bash
# QA contract checks against the deployed API.
#
# Small on purpose: a real service would run its integration suite here.
# The point is that the QA gate runs real checks, never a placeholder echo.
#
# Usage: scripts/integration-test.sh <url-of-GET-/hello>
set -euo pipefail

url="${1:?usage: integration-test.sh <url-of-GET-/hello>}"
base="${url%/hello}"

headers="$(mktemp)"
body="$(mktemp)"
trap 'rm -f "$headers" "$body"' EXIT

fail() { echo "::error::$*" >&2; exit 1; }
status() { curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "$@"; }

# 1. GET /hello returns the greeting as plain text.
code="$(curl --silent --show-error --max-time 10 --dump-header "$headers" --output "$body" --write-out '%{http_code}' "$url")"
[[ "$code" == "200" ]] || fail "GET /hello returned HTTP $code"
[[ "$(cat "$body")" == "Hello, World!" ]] || fail "GET /hello returned an unexpected body"
grep -qi '^content-type: text/plain' "$headers" || fail "GET /hello is not served as text/plain"
echo "ok 1 - GET /hello returns the greeting as text/plain"

# 2. Only GET is exposed on /hello.
code="$(status --request POST "$url")"
[[ "$code" =~ ^(403|404|405)$ ]] || fail "POST /hello returned HTTP $code; only GET should be exposed"
echo "ok 2 - POST /hello is rejected (HTTP $code)"

# 3. Nothing else is served.
code="$(status "$base/does-not-exist")"
[[ "$code" =~ ^(403|404)$ ]] || fail "An unknown path returned HTTP $code"
echo "ok 3 - unknown paths are rejected (HTTP $code)"
