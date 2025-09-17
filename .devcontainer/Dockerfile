FROM golang:1.24

RUN curl -sSf https://raw.githubusercontent.com/WasmEdge/WasmEdge/master/utils/install.sh | bash -s -- -p /usr/local

RUN apt update && apt install -y python3 pipx ssh-askpass
RUN pipx install --include-deps ansible --force
RUN pipx ensurepath

ENV LC_ALL="C.UTF-8"
ENV ANSIBLE_HOST_KEY_CHECKING=False