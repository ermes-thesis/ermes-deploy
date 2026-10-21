#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

src="../../ermes-generic-node"
binary="$(mktemp)"
trap 'rm -f "$binary"' EXIT

if [[ ! -d "$src" ]]; then
  echo "Missing source directory: $src" >&2
  exit 1
fi

if [[ ! -f ../../ermes-compilation/aarch64/main-aarch64 ]]; then
  echo "Missing ARM64 executable: ../../ermes-compilation/aarch64/main-aarch64" >&2
  exit 1
fi

echo "Building the amd64 node from $src"
GOOS=linux GOARCH=amd64 go build -C "$src" -ldflags="-s -w" -o "$binary" main

echo "Deploying the heterogeneous test"
ansible-playbook -i inventory.ini deploy.yml \
  -e "ermes_binary_amd64=$PWD/$binary"
