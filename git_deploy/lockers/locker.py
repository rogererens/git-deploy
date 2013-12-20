"""
Locking model that allows customized deploy locking bahaviour
"""

__date__ = '2013-12-20'
__license__ = 'GPL v2.0 (or later)'


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


class DeployLockerDefault(object):
    """
    Default Locker class
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
