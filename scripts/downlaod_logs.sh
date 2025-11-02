#!/bin/bash
NODES=("10.10.101.50" "10.10.101.51" "10.10.101.52" "10.10.101.53" "10.10.101.54" "10.10.101.55" "10.10.101.56" "10.10.101.57")
REMOTE_PATH="/var/log/ermes-node/*"
LOCAL_DIR="./logs"

rm -rf "$LOCAL_DIR"
mkdir -p "$LOCAL_DIR"

echo "🔹 Scarico log..."
for node in "${NODES[@]}"; do
    scp -J ubuntu@100.112.91.33 ubuntu@$node:$REMOTE_PATH "$LOCAL_DIR/$node/" && echo "✅ $node" &
done
wait
echo "✅ Tutti i log scaricati in $LOCAL_DIR/"
