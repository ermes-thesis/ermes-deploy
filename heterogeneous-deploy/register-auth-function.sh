#!/usr/bin/env bash
set -euo pipefail

wasm_path="$1"
registry_url="$2"
central_repo_url="$3"
dev_secret="$4"

payload="$(mktemp)"
trap 'rm -f "$payload"' EXIT

metadata='{"Name":"authFunction","Version":"1.0.0","TemplateNames":null,"DeployedOn":null,"StrongCollWriteAccess":false,"IsAuth":true}'
{
  printf '{"function":"'
  base64 "$wasm_path" | tr -d '\n'
  printf '","metadata":"'
  printf '%s' "$metadata" | base64 | tr -d '\n'
  printf '"}\n'
} > "$payload"

curl --fail --silent --show-error --retry 30 --retry-connrefused \
  -X POST "$registry_url/store-function" \
  -H 'Content-Type: application/json' \
  -H "X-DEV-SECRET: $dev_secret" \
  -H 'X-ERMES-OVERWRITE: true' \
  --data-binary "@$payload"

curl --fail --silent --show-error --retry 30 --retry-connrefused \
  -X PUT "$central_repo_url/set-auth-function/authFunction/1.0.0" \
  -H "X-DEV-SECRET: $dev_secret"
