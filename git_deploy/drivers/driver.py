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


def _call_hooks(path, phase, dryrun=False):
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
                if dryrun:
                    print ''
                    with open(cmd) as f:
                        for line in f.readlines():
                            if not line[-1] == '\n':
                                print '\t' + line[:-1]
                            else:
                                print '\t' + line[:-1]
                    print ''

                else:
                    proc = subprocess.Popen(path + '/' + item,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
                    log.info(cmd + ' OUT -> ' + '; '.join(
                        filter(lambda x: x, proc.communicate())))

                    # Flag a failed hook
                    if proc.returncode:
                        raise DeployDriverError(exit_code=17,
                                                message=exit_codes[17])

    else:
        log.error(__name__ + ' :: CANNOT FIND HOOK PATH \'{0}\''.format(
            path))
        raise DeployDriverError(exit_code=17, message=exit_codes[17])


def _make_release_tag(tag, author):
    """ Generates a release tag for the deploy """
    try:
        GitMethods()._dulwich_tag(tag, author)
    except Exception as e:
        log.error(str(e))
        raise DeployDriverError(message=exit_codes[12], exit_code=12)


class DeployDriverDefault(object):
    """ Driver class for custom hooks """

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployDriverDefault, cls).__new__(cls, *args,
                                                                    **kwargs)
        return cls.__instance

    def sync(self, args):
        """Call custom syncing behaviour.

        1. Call common pre-sync hooks
        2. Call app specific pre-sync hooks
        3. Call app sync
        4. Call app specific post-sync hooks
        5. Call common post-sync hooks

        """

        app_path = '{0}/{1}'.format(args['deploy_apps'], args['env'])

        # 1. CALL deploy/apps/common
        log.info('{0} :: Calling pre-sync common: "{1}" ...'.
            format(__name__, args['deploy_apps_common']))
        _call_hooks(args['deploy_apps_common'], 'pre-sync', args['dryrun'])

        # 2. CALL deploy/apps/$env
        if not args['default']:
            log.info('{0} :: Calling pre-sync app: "{1}" ...'.
                format(__name__, app_path))
            _call_hooks(app_path, 'pre-sync', args['dryrun'])

        # 3. Apply optional release tag here
        if args['release'] and not args['dryrun']:
            _make_release_tag(args['tag'], args['author'])

        # 4. CALL sync, deploy/apps/sync/$env.sync
        log.info('{0} :: Calling pre-sync app: "{1}" ...'.
            format(__name__, args['deploy_sync']))
        if args['default'] or not args['env']:
            _call_hooks(args['deploy_sync'], 'default', args['dryrun'])
        else:
            _call_hooks(args['deploy_sync'], args['env'], args['dryrun'])

        # 4. CALL app post sync, deploy/apps/$env
        if not args['default']:
            log.info('{0} :: Calling post-sync app: "{1}" ...'.
                format(__name__, app_path))
            _call_hooks(app_path, 'post-sync', args['dryrun'])

        # 4. CALL common post sync, deploy/apps/common
        log.info('{0} :: Calling post-sync app: "{1}" ...'.
            format(__name__, args['deploy_apps_common']))
        _call_hooks(args['deploy_apps_common'], 'post-sync', args['dryrun'])


class DeployDriverDryRun(object):
    """
    Dryrun Driver class.  This is a wrrapper over DeployDriverDefault.
    """

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(DeployDriverDryRun, cls).__new__(cls,
                                                                     *args,
                                                                     **kwargs)
        return cls.__instance

    def sync(self, args):

        log.info('{0} :: DRYRUN SYNC'.format(__name__))

        log.info('--> TAG \'{0}\''.format(args['tag']))
        log.info('--> AUTHOR \'{0}\''.format(args['author']))
        log.info('--> REMOTE \'{0}\''.format(args['remote']))
        log.info('--> BRANCH \'{0}\''.format(args['branch']))

        log.info('DUMPING DEPLOY SCRIPTS IN ORDER OF EXECUTION.')
        DeployDriverDefault().sync(args)

        log.info('{0} :: DRYRUN SYNC COMPLETE'.format(__name__))




