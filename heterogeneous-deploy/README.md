# Heterogeneous deployment

This directory contains an isolated deployment of Ermes across one amd64 cloud
node and one arm64 edge node. It is additive: it does not change the existing
roles, playbooks, inventories, or group variables outside this directory.

The deployment consists of:

- an Ermes node and Redis on each host;
- the Function Registry and Central Repo on the cloud node;
- MinIO for the central services;
- an optional 25 ms one-way delay between the cloud and edge nodes.

The inventory and topology used by this deployment are local to
[`inventory.ini`](./inventory.ini) and [`group_vars/all.yml`](./group_vars/all.yml).
The edge host is reached through the SSH alias `sola-pi`; its Ermes topology
address is kept separately as `node_address`.

## Prerequisites

Run the deployment from SOLA4 after cloning this repository and its sibling
source repositories there. The cloud node uses `ansible_connection=local`; only
the edge node is contacted over SSH.

The Ansible account must:

- already have Docker and Docker Compose installed on both hosts;
- be able to use Docker without `sudo`;
- have WasmEdge installed on both hosts;
- have Ansible, Go, and `curl`/`nc` available on SOLA4.

The default WasmEdge library path is
`/usr/local/lib/libwasmedge.so.0.1.0`. Override it when necessary:

```bash
ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/deploy.yml \
  -e wasmedge_host_library=/path/to/libwasmedge.so.0.1.0
```

The amd64 executable is built from `../../ermes-generic-node`. The arm64
executable defaults to `../../ermes-compilation/aarch64/main-aarch64`; override
it with `-e ermes_binary_arm64=/absolute/path/to/main-aarch64`.

The central deployment also requires these files:

```text
../../ermes-function-registry/ermes-function-registry
../../ermes-central-repo/ermes-central-repo
../../ermes-central-repo/keys/private.pem
../../ermes-central-repo/integration_test/authFunction@1.0.0.wasm
```

Build the local MinIO image required by the central deployment and verify its
tag before starting:

```bash
docker image inspect minio-local:legacy
```

Use `-e minio_image=<local-image:tag>` if the image has another tag.

## Deploy

Check Docker and SSH access first:

```bash
ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/check-prerequisites.yml

ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/ping.yml
```

Build the amd64 node, deploy both node stacks and the central services, then
apply the default cloud-edge latency:

```bash
./heterogeneous-deploy/deploy-heterogeneous.sh
```

The script accepts `--latency apply|reset`. To deploy without the wrapper, run
the playbooks directly:

```bash
ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/deploy.yml

ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/deploy-central.yml
```

The node stack is stored in `$HOME/ermes-heterogeneous`; the central stack is
stored in `$HOME/ermes-central-heterogeneous`. Both use host networking.
Node Redis uses port `6379`; central Redis uses `6380`. Central MinIO uses
the S3 API port `9091` and console port `9092`, while the Function Registry and
Central Repo use ports `8080` and `8081`.

## Verify

Inspect the node services on either host:

```bash
cd "$HOME/ermes-heterogeneous"
docker compose ps
docker compose logs --tail=100 ermes-node redis
```

The node logs are in `$HOME/ermes-heterogeneous/logs`. The central logs are in
`$HOME/ermes-central-heterogeneous/logs`.

Check Redis and the Ermes protocol ports from SOLA4:

```bash
redis-cli -h 10.79.10.134 -p 6379 PING
redis-cli -h 10.79.10.243 -p 6379 PING
nc -vz 10.79.10.134 12345
nc -vz 10.79.10.243 12345
```

Each Redis command should return `PONG`; an open port confirms that the Ermes
process is listening. Check central MinIO without credentials:

```bash
curl -i http://10.79.10.134:9091/minio/health/live
curl -i http://10.79.10.134:9091/minio/health/ready
```

Both requests should return HTTP `200`. The MinIO console is available at
<http://10.79.10.134:9092/>.

Apply or reset latency independently:

```bash
ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/apply_latency.yml -e latency_action=apply

ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/apply_latency.yml -e latency_action=reset
```

## Stop and remove

Stop and remove the containers while preserving their data volumes:

```bash
ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/stop.yml
```

To also remove the Redis and MinIO volumes, pass `purge_volumes=true`. This
deletes the deployment data:

```bash
ANSIBLE_CONFIG=heterogeneous-deploy/ansible.cfg \
  ansible-playbook -i heterogeneous-deploy/inventory.ini \
  heterogeneous-deploy/stop.yml -e purge_volumes=true
```
