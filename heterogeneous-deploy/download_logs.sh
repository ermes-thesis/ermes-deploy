#!/usr/bin/env bash
set -euo pipefail

SSH_USER="cenzato"
NODE_CONTAINER="ermes-heterogeneous-node"
NODE_LOG_FILE="/var/log/ermes-node/general.log"
CENTRAL_LOG_PATH="/home/cenzato/ermes-central-heterogeneous/logs/"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <logs-directory>" >&2
    exit 1
fi

LOCAL_DIR="$1"
[[ "${CENTRAL_LOG_PATH}" != */ ]] && CENTRAL_LOG_PATH="${CENTRAL_LOG_PATH}/"

rm -rf "$LOCAL_DIR"
mkdir -p "$LOCAL_DIR"

download_node_logs() {
    local node="$1"
    local method="$2"
    local target_dir="$LOCAL_DIR/$node"
    local target_file="$target_dir/general.log"

    mkdir -p "$target_dir"
    if [[ "$method" == "local" ]]; then
        docker cp "$NODE_CONTAINER:$NODE_LOG_FILE" "$target_file"
    else
        ssh -o StrictHostKeyChecking=no "$SSH_USER@sola-pi" \
            "docker exec $NODE_CONTAINER cat $NODE_LOG_FILE" > "$target_file"
    fi

    echo "✅ Node logs downloaded: $node"
}

echo "🔹 Downloading logs..."

# SOLA4 is the host running this script; only SOLA-PI requires SSH.
download_node_logs "sola4" "local" &
download_node_logs "sola-pi" "remote" &

mkdir -p "$LOCAL_DIR/central/function-registry" "$LOCAL_DIR/central/group-token"
rsync -az "$CENTRAL_LOG_PATH/function-registry/" \
    "$LOCAL_DIR/central/function-registry/" >/dev/null 2>&1 &
rsync -az "$CENTRAL_LOG_PATH/central-repo/" \
    "$LOCAL_DIR/central/group-token/" >/dev/null 2>&1 &

wait
echo "✅ All logs downloaded to $LOCAL_DIR"