"""
Handles logging related functionality for deployments
"""

__date__ = '2014-01-14'
__license__ = 'GPL v2.0 (or later)'

import re

from git_deploy.utils import ssh_command_target
from git_deploy.config import log


class DeployLogError(Exception):
    """ Basic exception class for DeployDriver types """
    def __init__(self, message="DeployDriver error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class DeployLogDefault(object):
    """
    Default Logging for deploy.

    Usage.  Active logging is entailed by calls to log with log lines.
    `log_archive` append-flushes the active log to the archive log.

    This is stored in a file on the target as specified in the singleton init.
    """

    LOGNAME_ARCHIVE = 'git-deploy.log'
    LOGNAME_ACTIVE = 'git-deploy-active.log'

    # class instance
    __instance = None

    def __init__(self, target, path, user, local_key_path):
        """ Initialize class instance """
        self.__class__.__instance = self

        self.target = target
        self.path = path + '/logs'
        self.user = user
        self.key_path = local_key_path

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployLogDefault, cls).__new__(cls)
        return cls.__instance

    def _check_and_add(self, path, filename):
        """
        Checks for a file and adds it if it's not there
        """
        cmd = 'ls {0} | grep -c {1}'.format(path, filename)
        ret = ssh_command_target(cmd, self.target, self.user, self.key_path)

        # Parse the count and add the file if it's missing
        if int(ret['stdout'][0].strip()) > 0:
            cmd = 'touch {0}/{1}'.format(path, filename)
            ssh_command_target(cmd, self.target, self.user, self.key_path)

    def log(self, line):
        """
        Handles log writing to remote file

        :param line: string; the line to be logged

        Returns True on successful logging, false otherwise.
        """

        self._check_and_add(self.path, self.LOGNAME_ACTIVE)

        # escape logline
        re.escape(line)
        cmd = "echo '{0}' >> {1}/{2}".format(line, self.path,
                                             self.LOGNAME_ACTIVE)
        # Write remote log line
        try:
            ssh_command_target(cmd, self.target, self.user, self.key_path)
        except:
            log.error("Failed to log '{0}'".format(line))
            return False

        return True

    def log_archive(self):
        """
        Dumps the active log to the archive. Returns True on successful
        logging, false otherwise.
        """

        self._check_and_add(self.path, self.LOGNAME_ARCHIVE)

        cmd = "cat {0}/{1} >> {2}/{3}".format(self.path,
                                              self.LOGNAME_ACTIVE,
                                              self.path,
                                              self.LOGNAME_ARCHIVE)
        # Write remote log line
        try:
            ssh_command_target(cmd, self.target, self.user, self.key_path)
        except:
            log.error("Failed to append active log to archive.")
            return False

        cmd = "rm {0}/{1}".format(self.path, self.LOGNAME_ACTIVE)

        # Write remote log line
        try:
            ssh_command_target(cmd, self.target, self.user, self.key_path)
        except:
            log.error("Failed to append active log to archive.")
            return False

        return True