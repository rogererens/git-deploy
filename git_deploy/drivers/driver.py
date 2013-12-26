"""
Driver model that allows customized deploy bahaviour
"""

__date__ = '2013-12-11'
__license__ = 'GPL v2.0 (or later)'

import subprocess
import os

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

    def _call_hooks(self, path, phase):
        """Performs calls on path/phase dependent hooks

        :param path: hooks path
        :param phase: deploy phase

        """
        if os.path.exists(path):
            sorted_path = sorted(os.listdir(path))
            for item in sorted_path:
                item_phase = item.split('.')[0]

                # CALL hook and log
                if phase == item_phase:
                    cmd = path + '/' + item
                    log_msg = 'CALLING \'{0}\' ON PHASE \'{1}\''.format(
                      cmd, phase
                    )
                    log.info(__name__ + ' :: {0}'.format(log_msg))
                    proc = subprocess.Popen(path + '/' + item,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                    log.info(cmd + ' OUT -> ' + '; '.join(
                        filter(lambda x: x, proc.communicate())))

                    # Flag a failed hook
                    if proc.returncode:
                        raise DeployDriverError(exit_code=17, message=exit_codes[17])

        else:
            log.error(__name__ + ' :: CANNOT FIND HOOK PATH \'{0}\''.format(
                path))
            raise DeployDriverError(exit_code=17, message=exit_codes[17])

    def sync(self, args):
        """Call custom syncing behaviour.

        1. Call common pre-sync hooks
        2. Call app specific pre-sync hooks
        3. Call app sync
        4. Call app specific post-sync hooks
        5. Call common post-sync hooks

        """

        # CALL deploy/apps/common
        self._call_hooks(args['deploy_apps_common'], 'pre-sync')

        # CALL deploy/apps/$env
        app_path = '{0}/{1}'.format(args['deploy_apps'], args.env)
        self._call_hooks(app_path , 'pre-sync')

        # CALL sync, deploy/apps/sync/$env.sync
        self._call_hooks(app_path , args.env)
        self._call_hooks(app_path , 'post-sync')
        self._call_hooks(args['deploy_apps_common'] , 'post-sync')
