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

from sartoris.config import GIT_CALL


def main():

    # Move to root - TODO, dulwich
    proc = subprocess.Popen([GIT_CALL, 'rev-parse', '--show-toplevel'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    os.chdir(proc.communicate()[0].strip())

    # Pull from remote -    TODO, dulwich
    #                       TODO, use git config for remote/branch
    proc = subprocess.Popen([GIT_CALL, 'pull', 'origin', 'master'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    proc.communicate()


def cli():
    sys.exit(main())

if __name__ == "__main__":  # pragma: nocover
    cli()
