# -*- coding: utf-8 -*-
# udb, A web interface to manage IT network
# Copyright (C) 2021 IKUS Software inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
from io import open

import setuptools

# Check running python version.
if not sys.version_info >= (3, 6):
    print('python version 3.6 is required.')
    sys.exit(1)

tests_require = [
    "pytest",
    "response",
]
extras_require = {'test': tests_require}

long_description = None
with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name='Universal Database',
    use_scm_version=True,
    description='Web application used to manage records to configure enterprise network with ansible-playbook.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Patrik Dufresne',
    author_email='patrik@ikus-soft.com',
    url='https://gitlab.com/ikus-soft/udb',
    license="GPLv3",
    packages=['udb'],
    package_dir={'': 'src'},
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "udb = udb.main:main",
        ],
    },
    install_requires=[
        "apscheduler",
        "babel",
        "CherryPy>18",
        "configargparse",
        "email_validator",
        "Jinja2",
        "ldap3",
        "requests",
        "sqlalchemy>=1.4,<1.5",
        "validators",
        "WTForms>=2.2.1",
    ],
    # required packages for build process
    setup_requires=[
        "setuptools_scm",
    ],
    # requirement for testing
    tests_require=tests_require,
    extras_require=extras_require,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Framework :: CherryPy',
    ],
    python_requires='!=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*, !=3.5.*, <4',
)
