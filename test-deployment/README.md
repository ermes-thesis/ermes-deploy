# Isolated heterogeneous deployment test

This directory is an additive test deployment. It does not change the existing
playbooks, roles, inventories, or group variables.

The playbooks use [`inventory.ini`](./inventory.ini), which defines
`cloud-node` (`amd64`) and `edge-node-1` (the Raspberry Pi, `arm64`). Docker
images are selected by Docker's multi-platform resolver:

- Redis runs on both nodes.
- MinIO runs on `cloud-node`.

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

The stop playbook also disables the Ermes systemd service so it does not start
again automatically. The Docker service itself is not stopped because it is
the host container runtime. To remove the persisted Redis and MinIO data
volumes as well, use:

```bash
ANSIBLE_CONFIG=test-deployment/ansible.cfg \
  ansible-playbook -i test-deployment/inventory.ini test-deployment/stop.yml \
  -e purge_volumes=true
```

`purge_volumes=true` is destructive for the test data. A later run of
`deploy-test.sh` recreates and starts the service and containers.

The script needs Go and Ansible on SOLA4. SOLA4 and the Raspberry need APT
access, and the Raspberry needs SSH privilege escalation. Docker, Redis, and
MinIO are installed and managed only by this test deployment.
