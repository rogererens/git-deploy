#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
    Prepares system state for Sartoris.
"""

import sys
import io
import logging
import ConfigParser

from sartoris.config import log

INI_FILE = '/your/project/home/scripts/sartoris.ini'

log_format = "%(asctime)s %(levelname)-8s %(message)s"
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter(fmt=log_format,
                     datefmt='%b-%d %H:%M:%S'))

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
            # TODO - process config  ... git config, cp git-deploy
            pass


def cli():
    sys.exit(main())

if __name__ == "__main__":  # pragma: nocover
    cli()
