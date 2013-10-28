#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Prepares system state for GitDeploy.
"""

import sys
import io
import logging
import ConfigParser
import subprocess
import shutil

INI_FILE = 'scripts/git-deploy.ini'

log_format = "%(asctime)s %(levelname)-8s %(message)s"
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter(fmt=log_format,
                     datefmt='%b-%d %H:%M:%S'))


def git_config_global_set(section, prop, value):
    proc = subprocess.Popen("git config --global {0}.{1} {2}".format(
        section, prop, value
    ).split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()


def main():

    # Process INI
    try:
        with file(INI_FILE, 'r') as f:
            config_handle = f.read()
        config = ConfigParser.RawConfigParser(allow_no_value=True)
        config.readfp(io.BytesIO(config_handle))
    except IOError:
        logging.error(__name__ + ' :: Could not find .ini.')
        return

    # Set the ini conf
    for section in config.sections():
        for name, value in config.items(section):
            # git config
            if section == 'deploy':
                git_config_global_set(section, name, value)

            # cp git-deploy
            if section == 'system' and name == 'run_root':
                shutil.copy('git_deploy/git_deploy', value)


def cli():
    sys.exit(main())

if __name__ == "__main__":  # pragma: nocover
    cli()
