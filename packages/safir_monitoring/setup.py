#!/usr/bin/env python
from setuptools import setup, find_packages

setup(
    name='safir_monitoring',
    version='1.0.0',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'safir_monitoring': [
            'db/alembic.ini',
            'db/alembic/*',
            'db/alembic/versions/*',
            'reporting/templates/*',
            'templates/*',
            'common/*.json',
        ]
    }
)
