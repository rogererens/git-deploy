#!/usr/bin/python
# -*- coding: utf-8 -*-

"""

Defult sync script that performs pull at the target.  The expected ops
are the following:

    cd $GIT_DEPLOY_HOME
    /usr/bin/git pull origin master

"""

import os
import sys
import subprocess

from git_deploy.config import GIT_CALL
from git_deploy.git_deploy import GitDeploy


def main():

    # Move to root - TODO, dulwich
    proc = subprocess.Popen([GIT_CALL, 'rev-parse', '--show-toplevel'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    os.chdir(proc.communicate()[0].strip())

    # Dulwich push
    GitDeploy()._dulwich_pull(GitDeploy().config['remote_url'])


def cli():
    sys.exit(main())

if __name__ == "__main__":  # pragma: nocover
    cli()
