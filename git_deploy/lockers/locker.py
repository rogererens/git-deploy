"""
Locking model that allows customized deploy locking bahaviour
"""

__date__ = '2013-12-20'
__license__ = 'GPL v2.0 (or later)'

from git_deploy.utils import ssh_command_target
from git_deploy.config import exit_codes, log

class DeployLockerError(Exception):
    """ Basic exception class for DeployLocker types """
    def __init__(self, message="DeployLocker error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class DeployLocker(object):
    """
    Abstract Locker interface
    """

    def get_lock_name(self, args):
        """
        lock instance name
        """
        raise NotImplementedError()


    def add_lock(self, args):
        """
        lock creation
        """
        raise NotImplementedError()

    def check_lock(self, args):
        """
        lock checking
        """
        raise NotImplementedError()

    def remove_lock(self, args):
        """
        lock removal
        """
        raise NotImplementedError()


class DeployLockerDefault(DeployLocker):
    """
    Default Locker class - implements a lock file
    """

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployLockerDefault, cls).__new__(cls,
                                                                     *args,
                                                                     **kwargs)
        return cls.__instance

    def get_lock_name(self, args):
        """ Generates the name of the lock file """
        return args.lock_handle + '-' + args.user + '.lock'

    def add_lock(self, args):
        """ Write the lock file """

        cmd = "touch {0}/{2}".format(
            args.deploy_path,
            self.get_lock_name(args))

        try:
            ret = ssh_command_target(cmd, args.target, args.user,
                                     args.key_path)
        except Exception as e:
            log.error(__name__ + ' :: ' + e.message)
            raise DeployLockerError(message=exit_codes[16], exit_code=16)

    def check_lock(self, args):
        """ Returns boolean flag on lock file existence """

        cmd = "ls {0}{1}{2}".format(
            args.deploy_path,
            args.get_lock_name())

        # log.debug('{0} :: Executing - "{1}"'.format(__name__, cmd))
        log.info('{0} :: Checking for lock file at {1}.'.format(
            __name__, args.target))

        try:
            ret = ssh_command_target(cmd, args.target, args.user,
                                     args.key_path)
        except Exception as e:
            log.error(__name__ + ' :: ' + e.message)
            raise DeployLockerError(message=exit_codes[16], exit_code=16)

        # Pull the lock file handle from
        try:
            file_handle = ret['stdout'][0].split('/')[-1].strip()
        except (IndexError, ValueError):
            log.info('{0} :: No lock file exists.'.format(__name__,
                                                          args.target))
            return False

        if file_handle == self.get_lock_name(args):
            log.info('{0} :: {1} has lock.'.format(__name__,
                                                   args.user))
            return True
        else:
            log.info('{0} :: Another user has lock.'.format(
                __name__, ))
            return False