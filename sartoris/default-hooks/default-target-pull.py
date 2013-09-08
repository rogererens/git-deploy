#!/usr/bin/python

"""

Defult sync script that performs pull at the target.  The expected ops
are the following:

    cd $GIT_DEPLOY_HOME
    /usr/bin/git pull origin master

"""

import sys


def main(args):
    pass


def cli():
    sys.exit(main(sys.argv))

if __name__ == "__main__":  # pragma: nocover
    cli()
