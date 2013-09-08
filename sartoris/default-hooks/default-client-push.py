#!/usr/bin/python

"""

Defult sync script that performs push from client.  The expected ops
are the following:

    cd $GIT_DEPLOY_HOME
    /usr/bin/git push origin master
    /usr/bin/git push --tags

"""

import sys


def main(args):
    pass


def cli():
    sys.exit(main(sys.argv))

if __name__ == "__main__":  # pragma: nocover
    cli()
