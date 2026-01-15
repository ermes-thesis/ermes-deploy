#!/bin/bash

NODES=("10.10.101.50" "10.10.101.51" "10.10.101.52" "10.10.101.53" "10.10.101.54" "10.10.101.55" "10.10.101.56" "10.10.101.57" "10.10.101.58")
JUMP_HOST="ubuntu@100.112.91.33"

# Rimuoviamo il wildcard qui per passarlo a rsync in modo sicuro
REMOTE_PATH="${1:-/var/log/ermes-node/}" 
# Assicuriamoci che il path finisca con /
[[ "${REMOTE_PATH}" != */ ]] && REMOTE_PATH="${REMOTE_PATH}/"

LOCAL_DIR="./logs"

rm -rf $LOCAL_DIR
mkdir -p $LOCAL_DIR

echo "🔹 Scarico log con rsync (compressione attiva)..."

for node in "${NODES[@]}"; do
    (
        NODE_ID="${node##*.}"
        TARGET_DIR="$LOCAL_DIR/$node"
        COMPLETE_FILE="$TARGET_DIR/general_$NODE_ID.log"
        
        mkdir -p "$TARGET_DIR"

        # --- MODIFICA CHIAVE QUI ---
        # 1. -a: archive mode (preserva tutto)
        # 2. -z: comprime i dati DURANTE il trasferimento (velocissimo per i file .log di testo)
        # 3. --include/--exclude: scarica solo quello che serve (più efficiente di *)
        # 4. -e: specifica il comando ssh con il Jump Host
        
        rsync -az \
            -e "ssh -J $JUMP_HOST -o StrictHostKeyChecking=no" \
            ubuntu@$node:$REMOTE_PATH \
            $TARGET_DIR/ \
            >/dev/null 2>&1
            
        echo "✅ File scaricati da $node"

        # Logica di processamento (Invariata ma ottimizzata per evitare errori se file non esistono)
        if compgen -G "$TARGET_DIR/general*.log.gz" > /dev/null; then
            gzip -dc "$TARGET_DIR"/general*.log.gz >> "$COMPLETE_FILE"
            rm "$TARGET_DIR"/general*.log.gz
        fi

        if [[ -f "$TARGET_DIR/general.log" ]]; then
            cat "$TARGET_DIR/general.log" >> "$COMPLETE_FILE"
            rm "$TARGET_DIR/general.log"
        fi

        echo "✅ Generato $COMPLETE_FILE"

    ) &
done
wait
echo "✅ Tutti i log scaricati in $LOCAL_DIR"