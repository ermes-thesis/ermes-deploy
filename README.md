# Ermes Deploy

Repository containing Ansible playbooks and configuration files needed to deploy and manage the Ermes framework.

## 📋 Requirements

To deploy Ermes you will need [Ansible](https://docs.ansible.com/)

### Option 1: DevContainer (Recommended)
The simplest way to run this project is using the provided **DevContainer**, which comes pre-installed with all necessary tools except for your SSH key.
If you add your SSH key to your local SSH agent, VS Code should automatically forward it to the container.

### Option 2: Manual Installation
> **Note:** Ansible is not natively available for Windows. Windows users should use WSL (Windows Subsystem for Linux).

This project requires a recent version of Ansible that is not typically available via standard `apt` repositories. We recommend installing it using `pipx`.

```bash
sudo apt update
sudo apt install python3 pipx
pipx install --include-deps ansible-core
pipx ensurepath
ansible --version
```

## 🔌 Connectivity Test

To test the connection with the remote machines you can run 

```bash
ansible -m ping nodes
ansible -m ping central_nodes
```

## 🚀 Deploy infrastructure

### Applying latencies

To apply simulated network latencies to the nodes:

```bash
ansible-playbook -i stateless apply-latency.yml
```

### Central node

This is the node that contains the Function registry and the Central repository.

The playbook expect:
- the function registry binary in `../ermes-function-registry/ermes-function-registry`
- the central repo binary in `../ermes-central-repo/ermes-central-repo`
- the central repo private key in `../ermes-central-repo/.devcontainer/private.pem`

Please manually build the executable in that position.
> The executable must be compiled for amd64 Linux platform (Golang compiler is provided in the DevContainer).

To deploy the central node the [Ansible minio role](https://github.com/ricsanfre/ansible-role-minio) is required.
If you use the DevContainer it is already installed, otherwise install it with:
```bash
ansible-galaxy role install ricsanfre.minio
```

To deploy:
```bash
ansible-playbook deploy-central-node.yml
```

The function registry and the central repo execute as systemd services on `vmsola-508`

### Ermes Nodes

To deploy the worker nodes, use the provided [wrapper script](./scripts/deploy.sh).
It expects the `ermes-generic-node` repository to be located in `../ermes-generic-node`.

First-time installation (installs dependencies):
```bash
./scripts/deploy.sh --install
```

Standard deployment:
```bash
./scripts/deploy.sh
```

Deploy with centralized configuration:
```bash
./scripts/deploy.sh --centralized
```
