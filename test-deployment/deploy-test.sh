#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

latency_action="apply"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --latency)
      if [[ $# -lt 2 || "$2" != "apply" && "$2" != "reset" ]]; then
        echo "Usage: $0 [--latency apply|reset]" >&2
        exit 1
      fi
      latency_action="$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--latency apply|reset]" >&2
      exit 1
      ;;
  esac
done

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

if [[ ! -f ../../ermes-function-registry/ermes-function-registry ]]; then
  echo "Missing Function registry executable: ../../ermes-function-registry/ermes-function-registry" >&2
  exit 1
fi

if [[ ! -f ../../ermes-central-repo/ermes-central-repo ]]; then
  echo "Missing Central repo executable: ../../ermes-central-repo/ermes-central-repo" >&2
  exit 1
fi

if [[ ! -f ../../ermes-central-repo/keys/private.pem ]]; then
  echo "Missing Central repo private key: ../../ermes-central-repo/keys/private.pem" >&2
  exit 1
fi

echo "Building the amd64 node from $src"
GOOS=linux GOARCH=amd64 ~/go/bin/go build -C "$src" -ldflags="-s -w" -o "$binary" main

echo "Deploying the heterogeneous test"
ansible-playbook -i inventory.ini deploy.yml \
  -e "ermes_binary_amd64=$binary"

echo "Deploying the central nodes to the cloud"
ansible-playbook -i inventory.ini deploy-central.yml

echo "Setting cloud-edge latency: $latency_action"
ansible-playbook -i inventory.ini apply_latency.yml \
  -e "latency_action=$latency_action"
