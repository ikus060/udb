# CMDB

<p align="center">
<a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-GPL--3.0-orange"></a>
<a href="https://gitlab.com/ikus-soft/cmdb/pipelines"><img alt="Build" src="https://gitlab.com/ikus-soft/cmdb/badges/master/pipeline.svg"></a>
<a href="https://sonar.ikus-soft.com/dashboard?id=cmdb"><img alt="Quality Gate Minarca Client" src="https://sonar.ikus-soft.com/api/project_badges/measure?project=cmdb&metric=alert_status"></a>
<a href="https://sonar.ikus-soft.com/dashboard?id=cmdb"><img alt="Coverage" src="https://sonar.ikus-soft.com/api/project_badges/measure?project=cmdb&metric=coverage"></a>
</p>

A web interface to manage IT network CMDB

## Installation

cmdb is not yet publish to pypi.org. You must install the project from source.

    pip install git:https://gitlab.com/ikus-soft/cmdb

## Usage

Once installed, you may start the application with default settings.

    cmdb

You may also customize more option when starting the application. To get a list of options available execute:

    cmdb --help

## Translation

Reference http://babel.edgewall.org/wiki/Documentation/setup.html

cmdb may be translated using `.po` files. This section describe briefly
how to translate the application. It's not a complete instruction set, it's merely a reminder.

Extract the strings to be translated:

    python setup.py extract_messages

Create a new translation:

    python setup.py init_catalog --local fr

Update an existing translation:

    python setup.py update_catalog --local fr

Compile catalog

    python setup.py compile_catalog
