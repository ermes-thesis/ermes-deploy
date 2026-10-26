# Isolated heterogeneous deployment test

This directory is an additive test deployment. It does not change the existing
playbooks, roles, inventories, or group variables.

The playbooks use [`inventory.ini`](./inventory.ini), which defines
`cloud-node` (`amd64`) and `edge-node-1` (the Raspberry Pi, `arm64`). Docker
images are selected by Docker's multi-platform resolver, except for MinIO,
which uses the locally built `minio-local:legacy` image:

- Redis runs on both nodes.
- MinIO runs on `cloud-node` from the local `minio-local:legacy` image.

The topology used by the node configuration is defined locally in
[`group_vars/all.yml`](./group_vars/all.yml), so this deployment does not
depend on the separate heterogeneous inventory variable files.
The inventory keeps the Raspberry SSH alias (`sola-pi`) separate from its
numeric Ermes topology address through `node_address`.

The amd64 Ermes executable is built from `../../ermes-generic-node`. The ARM64
executable defaults to the verified path
`../../ermes-compilation/aarch64/main-aarch64`. Override it with
`-e ermes_binary_arm64=/absolute/path/to/main-aarch64` if it is stored
elsewhere.

## Execution location and SSH routing

Clone this repository and its sibling source repositories on SOLA4, then run
the deployment from SOLA4. In [`inventory.ini`](./inventory.ini), `cloud-node`
uses `ansible_connection=local`, so the cloud deployment runs directly on the
machine executing Ansible. Its `ansible_host` remains `10.79.10.134` because
that address is used in the Ermes topology configuration.

Only `edge-node-1` is contacted remotely, through the `sola-pi` host alias.
This assumes that SOLA4 can resolve and reach `sola-pi` directly. If the alias,
address, or remote login user differs, update [`inventory.ini`](./inventory.ini).
No `sola3`/`sola4` proxy configuration is required by this deployment.

## Privileges

The deployment playbook does not install or start Docker and does not use
`sudo`, system-wide systemd, `/opt`, `/etc`, or `/var/log`. It uses the
preinstalled Docker Compose and stores all files below
`$HOME/ermes-test`. Redis, MinIO, and the Ermes node run as Compose services.

The account used by Ansible must already be allowed to use Docker without sudo
(normally by membership in the `docker` group). Run this read-only diagnostic:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini \
  test-deployment/check-prerequisites.yml
```

If `docker info` reports a permission error, the host Docker group/socket
permissions must be fixed by an administrator; the playbook intentionally does
not attempt that privileged change.

WasmEdge must be installed on both hosts because the Ermes executable is
dynamically linked against `libwasmedge.so.0`. The deployment mounts the host
library into the Ermes container. The default path is
`/usr/local/lib/libwasmedge.so.0.1.0`; override it when the library is installed
elsewhere:

```bash
ansible-playbook -i test-deployment/inventory.ini test-deployment/deploy.yml \
  -e wasmedge_host_library=/path/to/libwasmedge.so.0.1.0
```

MinIO uses the locally built `minio-local:legacy` image by default. The image
must be manuall built on SOLA4, following the instructions in the forked 
`MinIO` repository inside this organization; Compose will not pull it from a 
registry. Verify it before deploying:

```bash
docker image inspect minio-local:legacy
```

If the image has a different local tag, override it with
`-e minio_image=<local-image:tag>`. If MinIO is intentionally unavailable for a
diagnostic run, set `-e minio_enabled=false`; otherwise a missing local image
will prevent Compose from starting the cloud services.

## Run

First test local and SSH connectivity to both nodes:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini test-deployment/ping.yml
```

Then build the amd64 executable and deploy:

```bash
./test-deployment/deploy-test.sh
```

After changing the Compose template or variables, rerun the deployment so
Compose recreates the affected containers:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini test-deployment/deploy.yml
```

## Verify services

The Compose file uses host networking. The cloud node is reachable at
`10.79.10.134` and the edge node at `10.79.10.243`; these are the
`node_address` values in [`inventory.ini`](./inventory.ini). Run the following
checks from SOLA4, or run them directly on the corresponding host.

### Check container state and logs

On each host, inspect the Compose services from the deployment directory:

```bash
cd "$HOME/ermes-test"
docker compose ps
docker compose logs --tail=100 ermes-node redis
# Run this on cloud-node as well:
docker compose logs --tail=100 minio
```

All expected containers should have a `running`/`Up` state. The Ermes node
writes its logs under `$HOME/ermes-test/logs` on the host:

```bash
tail -n 100 "$HOME/ermes-test/logs/general.log"
tail -n 100 "$HOME/ermes-test/logs/ermes-node.err.log"
```

To inspect both hosts through Ansible:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible -i test-deployment/inventory.ini nodes \
  -m shell -a 'cd "$HOME/ermes-test" && docker compose ps'
```

### Check Redis

Redis runs on both nodes on TCP port `6381`. The test deployment uses this
separate port because host networking would otherwise collide with a Redis
instance already listening on the standard `6379`. From SOLA4, if `redis-cli` is
installed:

```bash
redis-cli -h 10.79.10.134 -p 6381 PING
redis-cli -h 10.79.10.243 -p 6381 PING
```

Each command should return `PONG`. If `redis-cli` is unavailable locally, run
the check on the target host through Docker:

```bash
ssh sola-pi 'docker exec ermes-test-redis redis-cli -p 6381 PING'
# On SOLA4:
docker exec ermes-test-redis redis-cli -p 6381 PING
```

### Check MinIO with curl

MinIO runs only on the cloud node. Its S3 API listens on port `9000`, and its
web console listens on port `9001`. The live and ready endpoints can be
checked without credentials:

```bash
curl -i http://10.79.10.134:9000/minio/health/live
curl -i http://10.79.10.134:9000/minio/health/ready
```

Both requests should return HTTP `200`. The console is reachable at
<http://10.79.10.134:9001/>; it is a web UI rather than a service health
endpoint.

### Check Ermes node connectivity

The Ermes node is a native binary using its own protocol on TCP port `12345`;
it does not expose an HTTP health endpoint in this deployment. Therefore,
`curl http://...:12345` is not a valid status check. Test that the protocol
port is accepting connections instead:

```bash
nc -vz 10.79.10.134 12345
nc -vz 10.79.10.243 12345
```

If `nc` is unavailable, use Bash's TCP check:

```bash
timeout 3 bash -c '</dev/tcp/10.79.10.134/12345' \
  && echo 'cloud Ermes port is open'
timeout 3 bash -c '</dev/tcp/10.79.10.243/12345' \
  && echo 'edge Ermes port is open'
```

An open port confirms that the process is listening; combine it with
`docker compose ps` and the Ermes logs to confirm that the node started
successfully and is not repeatedly restarting.

To stop the Ermes application and all Redis/MinIO containers while preserving
their data volumes:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini test-deployment/stop.yml
```

The stop playbook removes the Compose containers. The Docker service itself is
not stopped because it is the host container runtime. To remove the persisted
Redis and MinIO data volumes as well, use:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini test-deployment/stop.yml \
  -e purge_volumes=true
```

`purge_volumes=true` is destructive for the test data. A later run of
`deploy-test.sh` recreates and starts the service and containers.

The script needs Go and Ansible on SOLA4. Docker Compose must already be
installed and usable by the Ansible account on both machines. Docker, Redis,
MinIO, and the Ermes node are managed only by this test deployment.
