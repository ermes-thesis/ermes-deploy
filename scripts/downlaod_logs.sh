#!/bin/bash
NODES=("10.10.101.50" "10.10.101.51" "10.10.101.52" "10.10.101.53" "10.10.101.54" "10.10.101.55" "10.10.101.56" "10.10.101.57")
REMOTE_PATH="/var/log/ermes-node/*"
LOCAL_DIR="./logs"

rm -rf "$LOCAL_DIR"
mkdir -p "$LOCAL_DIR"

echo "🔹 Scarico log..."
for node in "${NODES[@]}"; do
    (
        TARGET_DIR="$LOCAL_DIR/$node"
        COMPLETE_FILE="$TARGET_DIR/complete.log"

        scp -J ubuntu@100.112.91.33 "ubuntu@$node:$REMOTE_PATH" "$TARGET_DIR/" >/dev/null 2>&1
        echo "✅ Scaricati log da $node"

        # Aggiunge i log decompressi
        if compgen -G "$TARGET_DIR/general-*.log.gz" > /dev/null; then
            echo "📦 Estrazione log compressi per $node..."
            gzip -dc "$TARGET_DIR"/general-*.log.gz >> "$COMPLETE_FILE"
            if [[ -f "$TARGET_DIR/general.log" ]]; then
                cat "$TARGET_DIR/general.log" >> "$COMPLETE_FILE"
            fi
        fi

        rm "$TARGET_DIR"/general*.log.gz "$TARGET_DIR"/general.log 2>/dev/null || true
        
        echo "✅ Creato $COMPLETE_FILE"

    ) &
done
wait
echo "✅ Tutti i log scaricati in $LOCAL_DIR"
