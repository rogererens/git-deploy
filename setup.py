#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from setuptools import setup

__version__ = '0.3.0'

meta = dict(
    name='git_deploy',
    version=__version__,
    description='Tool to manage using git as a deployment management tool',
    long_description=open('README.md').read(),
    author="Git Tools",
    author_email="preilly@php.net,bobs.ur.uncle@gmail.com",
    url='https://github.com/Git-Tools/git-deploy',
    packages=['git_deploy'],
    entry_points={
        'console_scripts': [
            'git-deploy = git_deploy.git_deploy_console:cli'
        ]
    },
    install_requires=[
        'dulwich',
        'paramiko >= 1.11.0',
    ],
    keywords=['git', 'deploy', 'scripts', 'cli'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Topic :: Utilities",
        "Topic :: Software Development :: Version Control",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: BSD License",
        "License :: OSI Approved :: MIT License",
    ],
    zip_safe=False,
    license="License :: OSI Approved :: BSD License",
)

# Automatic conversion for Python 3 requires distribute.
if False and sys.version_info >= (3,):
    meta.update(dict(
        use_2to3=True,
    ))

setup(**meta)