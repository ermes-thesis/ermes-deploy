#!/bin/bash
NODES=("10.10.101.50" "10.10.101.51" "10.10.101.52" "10.10.101.53" "10.10.101.54" "10.10.101.55" "10.10.101.56" "10.10.101.57")
REMOTE_PATH="/var/log/ermes-node/*"
LOCAL_DIR="./logs"

rm -rf $LOCAL_DIR
mkdir -p $LOCAL_DIR

echo 🔹 Scarico log...
for node in "${NODES[@]}"; do
    (
        NODE_ID="${node##*.}"
        TARGET_DIR="$LOCAL_DIR/$node"
        COMPLETE_FILE="$TARGET_DIR/general_$NODE_ID.log"
        
        mkdir -p "$TARGET_DIR"

        scp -J ubuntu@100.112.91.33 ubuntu@$node:$REMOTE_PATH $TARGET_DIR/ >/dev/null 2>&1
        echo ✅ Scaricati file temporanei da $node

        if compgen -G $TARGET_DIR/general*.log.gz > /dev/null; then
            gzip -dc $TARGET_DIR/general*.log.gz >> $COMPLETE_FILE
            rm $TARGET_DIR/general*.log.gz
        fi

        if [[ -f $TARGET_DIR/general.log ]]; then
            cat $TARGET_DIR/general.log >> $COMPLETE_FILE
            rm $TARGET_DIR/general.log
        fi

        echo ✅ Generato $COMPLETE_FILE

    ) &
done
wait
echo ✅ Tutti i log scaricati in $LOCAL_DIR
