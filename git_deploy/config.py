"""
Config file for GitDeploy.
"""

__authors__ = {
    'Ryan Faulkner': 'bobs.ur.uncle@gmail.com',
    'Patrick Reilly': 'preilly@php.net',
    'Ryan Lane': 'rlane@wikimedia.org',
}
__date__ = '2013-09-08'
__license__ = 'GPL v2.0 (or later)'

from dulwich.repo import Repo
import subprocess
from deploylog.deploylog import DeployLogDefault
import logging

# Native git call
GIT_CALL = '/usr/bin/git'

# DEFAULT DEPLOY HOOKS
DEFAULT_HOOK = 'default.sync'

DEFAULT_REMOTE = 'origin'
DEFAULT_BRANCH = 'master'

DEFAULT_REMOTE_ARG_IDX = 1
DEFAULT_BRANCH_ARG_IDX = 2

# Codes emitted on exit conditions
exit_codes = {
    1: 'Operation failed.  Exiting.',
    2: 'A deployment has already been started.  Exiting.',
    3: 'Please enter valid arguments.  Exiting.',
    4: 'Missing lock file.  Exiting.',
    5: 'Could not reset.  Exiting.',
    6: 'Diff failed.  Exiting.',
    7: 'Missing tag(s).  Exiting.',
    8: 'Could not find tag.  Exiting.',
    9: 'Could not get listing from deploy target.  Exiting.',
    10: 'Please specify number of deploy tags to emit with -c.  Exiting',
    11: 'Could not find any deploys.  Exiting',
    12: 'Tagging failed. Exiting',
    13: 'Revert tag not found. Exiting',
    14: 'Commit failed, does not match HEAD. Exiting.',
    15: 'Missing git config. Aborting.',
    16: 'SSH call failed. Aborting.',
    17: 'Call to deploy hook failed. Aborting.',
    18: 'Can\t initialize locker. Aborting.',
    19: 'Missing system configuration item "deploy.client-path". Exiting.',
    20: 'Cannot find top level directory for the git repository. Exiting.',
    21: 'Missing system configuration item "hook-dir". Exiting.',
    22: 'Missing repo configuration item "tag-prefix". '
        'Please configure this using:'
        '\n\tgit config tag-prefix <repo>',
    23: 'Missing system configuration item "path". Exiting.',
    24: 'Missing system configuration item "user". Exiting.',
    25: 'Missing system configuration item "target". Exiting.',
    28: 'Missing system configuration item "user.name". Exiting.',
    29: 'Missing system configuration item "user.email". Exiting.',
    30: 'No deploy started. Please run: git deploy start',
    31: 'Failed to write tag on sync. Exiting.',
    32: 'Failed to write the .deploy file. Exiting.',
    33: 'git revert failed. Exiting.',
    34: 'git log failed. Exiting.',
    35: 'Revert failed, could not find tag. Exiting.',
    36: 'Not enough tags (<2) to revert on. Exiting.',
    37: 'Missing system configuration item "key-path". Exiting.',
    38: 'Missing system configuration item "test-repo-path". Exiting.',
    39: 'Call to SSH failed. Exiting.',
    40: 'Failed to run sync script. Exiting.',
    41: 'Missing system configuration item "remote-url". Exiting.',
    50: 'Failed to read the .deploy file. Exiting.',
    60: 'Invalid git deploy action. Exiting.',
}


# NullHandler was added in Python 3.1.
try:
    NullHandler = logging.NullHandler
except AttributeError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

# Add a do-nothing NullHandler to the module logger to prevent "No handlers
# could be found" errors. The calling code can still add other, more useful
# handlers, or otherwise configure logging.
log = logging.getLogger(__name__)
log.addHandler(NullHandler())

global deploy_log
deploy_log = None


class GitDeployConfigError(Exception):
    """ Basic exception class for UserMetric types """
    def __init__(self, message="Git deploy error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


def set_log(args, out, err):
    """
    Sets the logger.

    Parameters:

        args    - command line args
        out     - stdout
        err     - stderr
    """
    level = logging.WARNING - ((args.verbose - args.quiet) * 10)
    if args.silent:
        level = logging.CRITICAL + 1

    log_format = "%(asctime)s %(levelname)-8s %(message)s"
    handler = logging.StreamHandler(err)
    handler.setFormatter(logging.Formatter(fmt=log_format,
                         datefmt='%b-%d %H:%M:%S'))
    log.addHandler(handler)
    log.setLevel(level)


def set_deploy_log(target, path, user, key_path):
    """ Sets the deploy logger to the target """
    global deploy_log
    if not deploy_log:
        deploy_log = DeployLogDefault(target, path, user, key_path)
    else:
        return deploy_log


def configure(**kwargs):
    """ Parse configuration from git config """
    config = {}

    # Get top level directory of project
    proc = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    config['top_dir'] = proc.communicate()[0].strip()
    _repo = Repo(config['top_dir'])
    sc = _repo.get_config_stack()

    if proc.returncode != 0:
        # log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
        raise GitDeployConfigError(message=exit_codes[20], exit_code=20)

    # Define the key names, git config names, and error codes
    config_elements = {
        'hook_dir': ('deploy', 'hook-dir', 21),
        'path': ('deploy', 'path', 23),
        'user': ('deploy', 'user', 24),
        'target': ('deploy', 'target', 25),
        'repo_name': ('deploy', 'tag-prefix', 22),
        'client_path': ('deploy', 'client-path', 19),
        'user.name': ('user', 'name', 28),
        'user.email': ('user', 'email', 29),
        'deploy.key_path': ('deploy', 'key-path', 37),
        'deploy.test_repo': ('deploy', 'test-repo-path', 38),
        'deploy.remote_url': ('deploy', 'remote-url', 41),
    }

    # Assign the values of each git config element
    for key, value in config_elements.iteritems():
        try:
            # Override with kwargs if the attribute exists
            if key in kwargs:
                config[key] = kwargs[key]
            else:
                config[key] = sc.get(value[0], value[1])
        except KeyError as e:
            log.error("{0} :: {1}".format(__name__, e.message))
            raise GitDeployConfigError(message=exit_codes[15], exit_code=15)

    config['sync_dir'] = '{0}/sync'.format(config['hook_dir'])

    config['deploy_root'] = config['client_path'] + '/.git/deploy'
    config['deploy_apps'] = config['deploy_root'] + '/apps'
    config['deploy_apps_common'] = config['deploy_root'] + '/apps/common'
    config['deploy_sync'] = config['deploy_root'] + '/sync'

    return config
