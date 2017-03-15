#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

version = 0.1

setup(
    name='flask-admin-django',
    version=str(version),
    author='',
    author_email='gbozee@gmail.com',
    packages=[
        'contrib_django',
    ],
    include_package_data=True,
    install_requires=[
        'django',
        'flask',
        'flask-admin',
    ],
    zip_safe=False,
)