# Isolated heterogeneous deployment test

This directory is an additive test deployment. It does not change the existing
playbooks, roles, inventories, or group variables.

The playbooks use [`inventory.ini`](./inventory.ini), which defines
`cloud-node` (`amd64`) and `edge-node-1` (the Raspberry Pi, `arm64`). Docker
images are selected by Docker's multi-platform resolver:

- Redis runs on both nodes.
- MinIO runs on `cloud-node`.

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

The MinIO image can be overridden with `-e minio_image=...`; it defaults to
`docker.io/minio/minio:latest`. Test registry access independently with
`docker pull docker.io/minio/minio:latest` or provide an image from a registry
available to the hardware. An authentication or registry-policy failure is
external to Ansible and prevents Compose from starting all services.

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
