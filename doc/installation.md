
# Installation

## System requirements

We recommend using high quality server hardware when running Universal Database in production.

### Minimum server requirement for evaluation

These minimum requirements are solely for evaluation and shall not be used in a production environment :

* Cpu 64bit x86-64 or amd64, 2 core
* Memory : 2 GiB RAM
* Hard drive/storage more than 8 GiB

### Recommended server requirement

* Cpu: 64bit x86-64 or amd64, 4 core
* Memory: minimum 4 GiB
* Hard drive/storage more than 8 GiB

## Install on Debian/Ubuntu repository

If you are running a Debian-based system, you should use `apt` to install Universal Database.

The following Debian Release are supported: Bookworm (12)

    apt install lsb-release
    curl -L https://nexus.ikus-soft.com/repository/archive/public.key | gpg --dearmor > /usr/share/keyrings/udb-keyring.gpg
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/udb-keyring.gpg] https://nexus.ikus-soft.com/repository/apt-release-$(lsb_release -sc)/ $(lsb_release -sc) main" > /etc/apt/sources.list.d/udb.list
    apt update
    apt install udb

> **_NOTE:_**  Access the web interface `http://<ip-or-dns-name>:8080` with username  **admin** and password **admin123**.
