# Universal Database

<p align="center">
<a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-orange"></a>
<a href="https://gitlab.com/ikus-soft/udb/pipelines"><img alt="Build" src="https://gitlab.com/ikus-soft/udb/badges/master/pipeline.svg"></a>
<a href="https://sonar.ikus-soft.com/dashboard?id=udb"><img alt="Quality Gate Minarca Client" src="https://sonar.ikus-soft.com/api/project_badges/measure?project=udb&metric=alert_status"></a>
<a href="https://sonar.ikus-soft.com/dashboard?id=udb"><img alt="Coverage" src="https://sonar.ikus-soft.com/api/project_badges/measure?project=udb&metric=coverage"></a>
<a href="https://www.djlint.com"><img alt="djlint" src="https://img.shields.io/badge/html%20style-djlint-blue.svg"></a>
</p>

A web interface to manage IT network

## Installation

Universal Database is available only for **Debian Bookworm**.

    apt update
    apt install apt-transport-https ca-certificates lsb-release gpg
    curl -L https://nexus.ikus-soft.com/repository/archive/public.key | gpg --dearmor > /usr/share/keyrings/ikus-soft-keyring.gpg
    echo "deb [arch=all signed-by=/usr/share/keyrings/ikus-soft-keyring.gpg] https://nexus.ikus-soft.com/repository/apt-release-$(lsb_release -sc)/ $(lsb_release -sc) main" > /etc/apt/sources.list.d/ikus-soft.list
    apt update
    apt install udb

## Usage

Once installed, you may start the application with default settings.

    udb

You may also customize more option when starting the application. To get a list of options available execute:

    udb --help

## Translation

Reference http://babel.edgewall.org/wiki/Documentation/setup.html

Universal Database may be translated using `.po` files. This section describe briefly
how to translate the application. It's not a complete instruction set, it's merely a reminder.

Extract the strings to be translated:

    tox -e babel_extract

Create a new translation:

    tox -e babel_init -- --locale fr

Update an existing translation:

    tox -e babel_update -- --locale fr 

Compile catalog

    tox -e babel_compile
