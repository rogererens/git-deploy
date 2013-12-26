"""
Driver model that allows customized deploy bahaviour
"""

__date__ = '2013-12-11'
__license__ = 'GPL v2.0 (or later)'

import subprocess
import os

from git_deploy.utils import ssh_command_target
from git_deploy.git_methods import GitMethods
from git_deploy.config import log, exit_codes, \
    DEFAULT_HOOK


class DeployDriverError(Exception):
    """ Basic exception class for DeployDriver types """
    def __init__(self, message="DeployDriver error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class DeployDriverDefault(object):
    """
    Default Driver class
    """

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployDriverDefault, cls).__new__(cls,
                                                                     *args,
                                                                     **kwargs)
        return cls.__instance

    def sync(self, args):

        #
        # Call deploy hook on client
        #
        #   {% PATH %}/.git/deploy/hooks/default-client-push origin master
        #

        try:
            GitMethods()._dulwich_tag(args['tag'], args['author'])
        except Exception as e:
            log.error(str(e))
            raise DeployDriverError(message=exit_codes[12], exit_code=12)

        sync_file = '{0}/{1}'.format(args['deploy_sync'], DEFAULT_HOOK)

        log.info('{0} :: Calling default sync \'{1}\' ... '.
            format(__name__, sync_file))

        proc = subprocess.Popen([sync_file,
            args['remote'],
            args['branch']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        log.info('SYNC OUT -> ' + '; '.join(
            filter(lambda x: x, proc.communicate())))


class DeployDriverCustom(object):
    """ Driver class for custom hooks """

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployDriverCustom, cls).__new__(cls, *args,
                                                                    **kwargs)
        return cls.__instance

    def sync(self, args):

        hook_path = "{0}/{1}".format(args['hook_dir'],
                                     args['hook_script'])

        # Call the sync script
        if os.path.exists(hook_path):
            log.info("{0} :: Calling sync "
                     "script at {1}".format(__name__,
                                            hook_path))

            sync_cmd = "{0} --repo {1} --tag {2}".format(
                hook_path,
                args['repo_name'],
                args['tag']
            )
            if args['force']:
                sync_cmd = sync_cmd + ' --force'
            proc = subprocess.Popen(sync_cmd.split())
            proc_out = proc.communicate()[0]

            if proc.returncode != 0:
                exit_code = 40
                log.error("{0} :: {1}".format(__name__,
                                              exit_codes[exit_code]))
                return exit_code

            log.info("{0} :: SYNC SCRIPT OUT-> {1}".format(
                __name__,
                proc_out))
