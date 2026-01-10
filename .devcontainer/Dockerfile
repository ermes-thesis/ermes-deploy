FROM golang:1.25

RUN curl -sSf https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | bash -s -- -p /usr/local

RUN apt update && apt install -y python3 pipx ssh-askpass curl tar xz-utils python3-requests && rm -rf /var/lib/apt/lists/*
RUN pipx install --include-deps ansible-core
RUN pipx install ansible-lint
RUN pipx ensurepath

RUN /root/.local/bin/ansible-galaxy role install ricsanfre.minio
RUN /root/.local/bin/ansible-galaxy collection install community.general

ENV LC_ALL="C.UTF-8"