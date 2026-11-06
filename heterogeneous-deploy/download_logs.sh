#!/usr/bin/env bash
set -euo pipefail

SSH_USER="cenzato"
NODE_LOG_PATH="${1:-/home/cenzato/ermes-heterogeneous/logs/}"
CENTRAL_LOG_PATH="${2:-/home/cenzato/ermes-central-heterogeneous/logs/}"
LOCAL_DIR="${3:-./logs}"

[[ "${NODE_LOG_PATH}" != */ ]] && NODE_LOG_PATH="${NODE_LOG_PATH}/"
[[ "${CENTRAL_LOG_PATH}" != */ ]] && CENTRAL_LOG_PATH="${CENTRAL_LOG_PATH}/"

rm -rf "$LOCAL_DIR"
mkdir -p "$LOCAL_DIR"

download_node_logs() {
    local node="$1"
    local source="$2"
    local target_dir="$LOCAL_DIR/$node"
    local complete_file="$target_dir/general.log"

    mkdir -p "$target_dir"
    rsync -az "$source" "$target_dir/" >/dev/null 2>&1

    if compgen -G "$target_dir/general*.log.gz" > /dev/null; then
        gzip -dc "$target_dir"/general*.log.gz >> "$complete_file"
        rm "$target_dir"/general*.log.gz
    fi

    if [[ -f "$target_dir/general.log" && "$target_dir/general.log" != "$complete_file" ]]; then
        cat "$target_dir/general.log" >> "$complete_file"
        rm "$target_dir/general.log"
    fi

    echo "✅ Log del nodo scaricati: $node"
}

echo "🔹 Scarico i log dei nodi e dei servizi centrali..."

# SOLA4 is the host running this script; only SOLA-PI requires SSH.
download_node_logs "sola4" "$NODE_LOG_PATH" &
download_node_logs "sola-pi" "$SSH_USER@sola-pi:$NODE_LOG_PATH" &

mkdir -p "$LOCAL_DIR/central/function-registry" "$LOCAL_DIR/central/group-token"
rsync -az "$CENTRAL_LOG_PATH/function-registry/" \
    "$LOCAL_DIR/central/function-registry/" >/dev/null 2>&1 &
rsync -az "$CENTRAL_LOG_PATH/central-repo/" \
    "$LOCAL_DIR/central/group-token/" >/dev/null 2>&1 &

wait
echo "✅ Tutti i log scaricati in $LOCAL_DIR"
