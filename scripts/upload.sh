#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

scp scripts/*.py ubuntu@100.112.91.33:/home/ubuntu