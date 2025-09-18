# Ermes Deploy

Repository containing Ansible playbooks and configuration files needed to deploy and manage the Ermes framework.

## Requirements

To deploy Ermes you will need [Ansible](https://docs.ansible.com/)

The simplest way to run this project is with the provided **DevContainer**, that contains all the necessary except of the ssh key.
If you add your ssh key to the ssh agent, vscode should automatically forword it to the container.

Otherwise, you can install manually all the requirements.

> Ansible is not available for Windows, but you can use WSL.

This project requires a recent version of Ansible, not available on `apt`, that need to be installed with `pip` or `pipx`.

To install:

```bash
sudo apt update
sudo apt install python3 pipx
pipx install --include-deps ansible-core
pipx ensurepath
ansible --version
```

## Test ssh connection

To test the connection with the remote machines you can run 

```bash
ansible -i inventory.ini -m ping nodes
ansible -i inventory.ini -m ping central_nodes
```

## Deploy infrastructure

### Central node

This is the node that contains the Function registry and the Central repository.

The playbook expect:
- the function registry binary in `../ermes-function-registry/ermes-function-registry`, 
- the central repo binary in `../ermes-central-repo/ermes-central-repo`, 
- the central repo private key in `../ermes-central-repo/.devcontainer/private.pem`, 
Please manually build the executable in that position.
The executable must be compiled for amd64 Linux platform (Golang compiler is provided in the DevContainer).

On Windows you can use:
```bash
set GOOS=linux
set GOARCH=amd64
go build .
```

To deploy the central node the [Ansible minio role](https://github.com/ricsanfre/ansible-role-minio) and the [Ansible role redis](https://github.com/geerlingguy/ansible-role-redis) are required.
If you use the DevContainer they are already installed, otherwise install them with:
```bash
ansible-galaxy role install ricsanfre.minio
ansible-galaxy role install geerlingguy.redis
```

To deploy:
```bash
ansible-playbook -i inventory.ini deploy-central-node.yml
```

The function registry and the central repo execute as systemd services on `vmsola-508`