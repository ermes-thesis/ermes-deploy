# Ermes Deploy

Ansible playbooks and configuration files to deploy and manage the Ermes
platform. The end-to-end deployment procedure (build, inventories, deploy
order) is described in the package top-level `README.md`; this file documents
the pieces this repository provides.

## Requirements

- `ansible-core` (recent version, e.g. via `pipx`):
  ```bash
  pipx install --include-deps ansible-core
  pipx ensurepath
  ansible --version
  ```
- Ansible roles/collections:
  ```bash
  ansible-galaxy role install ricsanfre.minio
  ansible-galaxy collection install community.general
  ```
- SSH access to every node with **passwordless sudo** for the Ansible user.
- On macOS control machines, export before any playbook:
  `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` and `no_proxy='*'`.

> **Note:** Ansible is not natively available on Windows; use WSL.

## Inventories

One inventory per experimental configuration (same machines, different node
behaviour): `inventories/stateful` (Ermes), `inventories/stateless`
(Cloud-Data), `inventories/cloud_only` (Cloud-Only). Each contains
`inventory.ini` (host IPs, groups, jump host) and `group_vars/` (topology and
the `common` node-config block). Edit these to match your cluster.

## Connectivity test

```bash
ansible -i inventories/stateful/inventory.ini -m ping nodes
ansible -i inventories/stateful/inventory.ini -m ping central_nodes
```

## Playbooks

### Network latencies

Injects the inter-tier RTTs with `tc`/NetEm, from each node's `latency_up`:
```bash
ansible-playbook -i inventories/<config>/inventory.ini apply_latency.yml
```

### Client-Cloud latencies

Manual RTT injection between client and cloud nodes for Enoki test comparison:
```bash
./scripts/apply_latency_client_cloud.sh
```

Edit the configuration variables (IPs, proxyjumps) inside it as needed.

### Central node

Deploys the Function Registry, the Central Repository (GTP), MinIO, and Redis:
```bash
ansible-playbook -i inventories/<config>/inventory.ini deploy-central-node.yml
```
The playbook expects the binaries to be built beforehand (see the top-level
README, Section 3):
- `../ermes-function-registry/ermes-function-registry`
- `../ermes-central-repo/ermes-central-repo`
- the GTP private key in `../ermes-central-repo/keys/private.pem`

Both run as systemd services on the central node.

### Worker nodes

```bash
ansible-playbook -i inventories/<config>/inventory.ini deploy-ermes-nodes.yml \
  -e bin_path=/tmp/ermes-node-build/ermes-node -e skip_install=false -e flush=true
```
- `bin_path`: path of the locally-built `ermes-node` binary; the playbook
  uploads `<bin_path>.tar.xz` (create it with
  `tar -Jcf ermes-node.tar.xz ermes-node`).
- `skip_install=true`: skip dependency installation (Redis, WasmEdge) when only
  updating the binary/config.
- `flush=true`: reset the platform state before starting.

To only reset the platform state: `flush-ermes-nodes.yml`.

### Utility scripts

- `scripts/deploy.sh`: wrapper for the worker-node deployment.
- `scripts/download_logs.sh`: fetch the per-node `general.log` files (uses
  `rsync --rsync-path="sudo rsync"` since the logs are root-owned).
