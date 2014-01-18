"""
Handles logging related functionality for deployments
"""

__date__ = '2014-01-14'
__license__ = 'GPL v2.0 (or later)'


class DeployLogError(Exception):
    """ Basic exception class for DeployDriver types """
    def __init__(self, message="DeployDriver error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class DeployLogDefault(object):
    """ Default Logging for deploy """

    LOGNAME = 'git-deploy.log'

    # class instance
    __instance = None

    def __init__(self, target, path, user, local_key_path):
        """ Initialize class instance """
        self.__class__.__instance = self

        self.target = target
        self.path = path
        self.user = user
        self.key_path = local_key_path

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployLogDefault, cls).__new__(cls)
        return cls.__instance

    def log(self, args):
        raise NotImplementedError()