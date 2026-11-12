#!/usr/bin/env bash

# This file remotely applies the latency rules used for the Enoki comparison test.

set -euo pipefail

PROXYJUMP="sola5remote"
REMOTE_USER="ubuntu"
CLIENT_IPS=("10.10.101.59" "10.10.101.60")
CLOUD_IP="10.10.101.57"
RTT=30
INTERFACE="eth0"

# Ansible constants (unchanged)
HTB_RATE="1000mbit"
PARENT_PREFIX="10"   # Part 1: node <-> direct parent (here: client <-> cloud)

DRY_RUN="${DRY_RUN:-0}"
CLEAN=0
VERIFY=0

usage() {
  cat <<EOF
Usage: $0 [--clean] [--verify]
  (no flags)  apply the latency configuration on all nodes
  --clean     remove all tc rules from the interface on every node
  --verify    after applying, show tc state and measure client -> cloud RTT
  DRY_RUN=1   print the per-node commands, touch nothing
EOF
}

for arg in "$@"; do
  case "$arg" in
    --clean)   CLEAN=1 ;;
    --verify)  VERIFY=1 ;;
    -h|--help) usage; exit 0 ;;
    *)         echo "Unknown argument: $arg" >&2; usage >&2; exit 1 ;;
  esac
done

SSH_OPTS=(-J "${PROXYJUMP}" -o BatchMode=yes -o ConnectTimeout=10)

# ---------------------------------------------------------------- validation
ipv4_re='^([0-9]{1,3}\.){3}[0-9]{1,3}$'
for ip in "${CLIENT_IPS[@]}" "${CLOUD_IP}"; do
  [[ $ip =~ $ipv4_re ]] || { echo "Invalid IPv4: $ip" >&2; exit 1; }
  # tc handles/classids are 16-bit hex: "<prefix><octet>" must fit in 4 digits.
  (( ${ip##*.} < 100 )) || { echo "Last octet of $ip >= 100: '${PARENT_PREFIX}<octet>' would exceed the 16-bit tc handle range" >&2; exit 1; }
done
for ip in "${CLIENT_IPS[@]}"; do
  [[ $ip != "$CLOUD_IP" ]] || { echo "Cloud IP must not be in CLIENT_IPS" >&2; exit 1; }
done
[[ $RTT =~ ^[0-9]+$ ]] || { echo "RTT must be a non-negative integer" >&2; exit 1; }

# Same split as Ansible: local = floor(RTT/2), remote = RTT - local
LAT_LOCAL=$(( RTT / 2 ))
LAT_REMOTE=$(( RTT - LAT_LOCAL ))

ALL_NODES=("${CLIENT_IPS[@]}" "${CLOUD_IP}")

# ------------------------------------------------------------------- helpers
# remote_exec <ip> : executes the script read from stdin as root on <ip>
remote_exec() {
  local ip=$1
  if [[ $DRY_RUN == 1 ]]; then
    echo "### [dry-run] ${REMOTE_USER}@${ip} via ${PROXYJUMP}"
    cat
    return 0
  fi
  echo ">>> ${ip}"
  ssh "${SSH_OPTS[@]}" "${REMOTE_USER}@${ip}" 'sudo bash -se'
}

# emit_rule <prefix> <peer_ip> <delay_ms>
# Same three-command chain as the Ansible shell tasks (class, netem qdisc, u32 filter).
emit_rule() {
  local prefix=$1 peer_ip=$2 delay=$3
  local id="${prefix}${peer_ip##*.}"
  cat <<EOF
tc class replace dev ${INTERFACE} parent 1:1 classid 1:${id} htb rate ${HTB_RATE}
tc qdisc replace dev ${INTERFACE} parent 1:${id} handle ${id}: netem delay ${delay}ms
tc filter replace dev ${INTERFACE} parent 1:0 protocol ip prio 10 u32 match ip dst ${peer_ip}/32 flowid 1:${id}
EOF
}

# node_script <ip> : complete root script for one node
# Each client's direct parent is the cloud, so Ansible Part 1 applies (prefix 10);
# Part 2 (overlay -> cloud) is skipped as parent == cloud, Part 3 (central
# storage) is skipped as the topology has no storage node.
node_script() {
  local ip=$1 c
  echo "set -e"
  if [[ $CLEAN == 1 ]]; then
    cat <<EOF
tc qdisc del dev ${INTERFACE} root || true
tc qdisc show dev ${INTERFACE}
EOF
    return 0
  fi
  cat <<EOF
modprobe sch_htb
tc qdisc del dev ${INTERFACE} root || true
tc qdisc replace dev ${INTERFACE} root handle 1: htb default 10
tc class replace dev ${INTERFACE} parent 1: classid 1:1 htb rate ${HTB_RATE}
tc class replace dev ${INTERFACE} parent 1:1 classid 1:10 htb rate ${HTB_RATE}
EOF
  if [[ $ip == "$CLOUD_IP" ]]; then
    # DOWN side: cloud -> each client, delay LAT_REMOTE
    for c in "${CLIENT_IPS[@]}"; do emit_rule "${PARENT_PREFIX}" "$c" "${LAT_REMOTE}"; done
  else
    # UP side: client -> cloud, delay LAT_LOCAL
    emit_rule "${PARENT_PREFIX}" "${CLOUD_IP}" "${LAT_LOCAL}"
  fi
}

# --------------------------------------------------------------------- main
if [[ $CLEAN == 1 ]]; then
  echo "=== Clean: removing tc configuration from ${INTERFACE} ==="
else
  echo "=== Apply: RTT=${RTT}ms (${LAT_LOCAL}ms local + ${LAT_REMOTE}ms remote) ==="
fi
for ip in "${ALL_NODES[@]}"; do
  node_script "$ip" | remote_exec "$ip"
done

# ------------------------------------------- optional verification (--verify)
if [[ $VERIFY == 1 && $CLEAN == 0 && $DRY_RUN != 1 ]]; then
  echo "=== Verification: installed qdiscs/filters ==="
  for ip in "${ALL_NODES[@]}"; do
    remote_exec "$ip" <<EOF
echo "--- qdisc"; tc qdisc show dev ${INTERFACE}
echo "--- filter"; tc filter show dev ${INTERFACE} parent 1:0
EOF
  done
  echo "=== Verification: measured RTT client -> cloud (expect ~${RTT}ms + base RTT) ==="
  for client in "${CLIENT_IPS[@]}"; do
    echo "ping ${client} -> ${CLOUD_IP}"
    remote_exec "${client}" <<EOF || echo "ping failed (non-fatal)"
ping -c 5 -q ${CLOUD_IP} | tail -n 2
EOF
  done
fi

echo "Done."