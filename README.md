# Ermes Deploy

Repository containing Ansible playbooks and configuration files needed to deploy and manage the Ermes framework.

## Requirements

To deploy Ermes you will need [Ansible](https://docs.ansible.com/)

> Ansible is not available for Windows, but you can use WSL.

This project requires a recent version of Ansible, not available on `apt`, that need to be installed with `pip` or `pipx`.

Suggested way to install:

```shell
sudo apt update
sudo apt install python3 pipx
pipx install --include-deps ansible
pipx ensurepath
ansible --version
```

## Test ssh connection

To test the connection with the remote machines you can run 

```shell
ansible -i inventory.ini -m ping nodes
ansible -i inventory.ini -m ping central_nodes
```

## Deploy infrastructure

### Function registry

The playbook expect the function registry binary to be in `../ermes-function-registry/ermes-function-registry`.
Please manually build the executable in that position.
The executable must be compiled for amd64 Linux platform, on Windows use WSL or compile with:
```shell
set GOOS=linux
set GOARCH=amd64
go build .
```

To deploy the Function Registry the [Ansible minio role](https://github.com/ricsanfre/ansible-role-minio) is required.
Install it with 
```shell
ansible-galaxy role install ricsanfre.minio
```

To deploy:
```shell
ansible-playbook -i inventory.ini deploy-central.yml
```

The function registry executes as a systemd service on `vmsola-508`