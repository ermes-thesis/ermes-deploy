#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

BIN_NAME="ermes-node"
SRC="../ermes-generic-node"
PLAYBOOK="deploy-ermes-nodes.yml"
TMPDIR="$(mktemp -d)"
BIN="$TMPDIR/$BIN_NAME"

log() { echo -e "\033[1;34m[INFO]\033[0m $*"; }
error() { echo -e "\033[1;31m[ERRORE]\033[0m $*" >&2; exit 1; }

# === Step 1: Build ===
log "Compilazione Go..."
if [[ ! -d "$SRC" ]]; then
  error "Directory sorgente non trovata: $SRC"
fi
GOOS=linux GOARCH=amd64 go build -C "$SRC" -ldflags="-s -w" -o "$BIN" main
log "Binario creato in $BIN"

# === Step 2: Compressione ===
log "Compressione binario..."
tar --sort=name \
    --mtime="" \
    --owner=0 --group=0 --numeric-owner \
    --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
    -Jcf "$BIN.tar.xz" -C "$TMPDIR" "$BIN_NAME"
log "Archivio creato: $BIN.tar.xz"

# === Step 3: Deploy con Ansible ===
log "Deploy con Ansible..."
ansible-playbook "$PLAYBOOK" -e "bin_path=$BIN" -e "skip_install=true" -e "flush=true"

# === Step 4: Pulizia ===
log "Pulizia temporanei..."
rm -rf "$TMPDIR"

log "✅ Deploy completato con successo!"
