"""
Locking model that allows customized deploy locking bahaviour
"""

__date__ = '2013-12-20'
__license__ = 'GPL v2.0 (or later)'

from git_deploy.utils import ssh_command_target
from git_deploy.config import exit_codes, log, deploy_log

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

    def get_lock_name(self):
        """
        lock instance name
        """
        raise NotImplementedError()


    def add_lock(self):
        """
        lock creation
        """
        raise NotImplementedError()

    def check_lock(self):
        """
        lock checking
        """
        raise NotImplementedError()

    def remove_lock(self):
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

        try:
            self.deploy_path = kwargs['deploy_path']
            self.target = kwargs['target']
            self.user = kwargs['user']
            self.key_path = kwargs['key_path']
            self.lock_handle = kwargs['lock_handle']

        except KeyError:
            raise DeployLockerError(message=exit_codes[18], exit_code=18)

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployLockerDefault, cls).__new__(cls,
                                                                     *args,
                                                                     **kwargs)
        return cls.__instance

    def get_lock_name(self):
        """ Generates the name of the lock file """
        return self.lock_handle + '-' + self.user + '.lock'

    def add_lock(self):
        """ Write the lock file """

        cmd = "touch {0}/{1}".format(self.deploy_path,
                                     self.get_lock_name())
        try:
            ssh_command_target(cmd, self.target, self.user,
                                     self.key_path)
        except Exception as e:
            log.error(__name__ + ' :: Failed to create lock -> ' + e.message)
            raise DeployLockerError(message=exit_codes[16], exit_code=16)

        # Logging
        log.info('{0} :: Created lock file at {1}:{2}/{3}.'.format(
            __name__, self.target, self.deploy_path, self.get_lock_name()))
        deploy_log.log('Created lock.')

    def check_lock(self):
        """ Returns boolean flag on lock file existence """

        cmd = "ls {0}/{1}".format(self.deploy_path, self.get_lock_name())

        # log.debug('{0} :: Executing - "{1}"'.format(__name__, cmd))
        log.info('{0} :: Checking for lock file at {1}.'.format(
            __name__, self.target))

        try:
            ret = ssh_command_target(cmd, self.target, self.user,
                                     self.key_path)
        except Exception as e:
            log.error(__name__ + ' :: ' + e.message)
            raise DeployLockerError(message=exit_codes[16], exit_code=16)

        # Pull the lock file handle from
        try:
            file_handle = ret['stdout'][0].split('/')[-1].strip()
        except (IndexError, ValueError):
            log.info('{0} :: No lock file exists.'.format(__name__,
                                                          self.target))
            return False

        if file_handle == self.get_lock_name():
            log.info('{0} :: {1} has lock.'.format(__name__,
                                                   self.user))
            return True
        else:
            log.info('{0} :: Another user has lock.'.format(__name__))
            return False

    def remove_lock(self):
        """ Remove the lock file """
        log.info('{0} :: SSH Lock destroy.'.format(__name__))

        cmd = "rm {0}/{1}".format(self.deploy_path, self.get_lock_name())

        try:
            ssh_command_target(cmd, self.target, self.user, self.key_path)
        except Exception as e:
            log.error(__name__ + ' :: Failed ot remove lock -> ' + e.message)
            raise DeployLockerError(message=exit_codes[16], exit_code=16)

        # Logging
        log.info('{0} :: Removed lock file at {1}:{2}/{3}.'.format(
            __name__, self.target, self.deploy_path, self.get_lock_name()))
        deploy_log.log('Removed lock.')