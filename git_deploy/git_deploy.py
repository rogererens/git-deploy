"""
This module defines the entities utilized to operate the git-deploy system
defined by the GitDeploy project.
"""

__authors__ = {
    'Ryan Faulkner': 'bobs.ur.uncle@gmail.com',
    'Patrick Reilly': 'preilly@php.net',
    'Ryan Lane': 'rlane@wikimedia.org',
}
__date__ = '2013-09-08'
__license__ = 'GPL v2.0 (or later)'

import os

from lockers.locker import DeployLockerDefault
from git_methods import GitMethods
from drivers.driver import DeployDriverDefault, DeployDriverDryRun
from config import deploy_log, set_deploy_log, log, configure, exit_codes, \
    DEFAULT_BRANCH, DEFAULT_REMOTE, \
    DEFAULT_REMOTE_ARG_IDX, DEFAULT_BRANCH_ARG_IDX


class GitDeployError(Exception):
    """ Basic exception class for UserMetric types """
    def __init__(self, message="Git deploy error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class GitDeploy(object):

    # Pattern for git-deploy tags
    TAG_PATTERN = r'[a-zA-Z]*-[0-9]{8}-[0-9]{6}'

    # Name of deployment directory
    DEPLOY_DIR = '.git/deploy/'

    # Name of lock file
    LOCK_FILE_HANDLE = 'lock'

    # Default tag message
    DEFAULT_TAG_MSG = 'GitDeploy Tag.'

    # Default tag message
    DEFAULT_COMMIT_MSG = 'GitDeploy Commit'

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

        if not os.path.exists(self.DEPLOY_DIR):
            os.mkdir(self.DEPLOY_DIR)

        # Locking model
        self._locker = DeployLockerDefault(
            deploy_path=self.config['path'] + self.DEPLOY_DIR,
            target=self.config['target'],
            user=self.config['user.name'],
            key_path=self.config['deploy.key_path'],
            lock_handle=self.LOCK_FILE_HANDLE
        )

        # Deploy Logger
        set_deploy_log(
            self.config['target'],
            self.config['path'] + self.DEPLOY_DIR,
            self.config['user.name'],
            self.config['deploy.key_path']
        )
        self.deploy_log = deploy_log

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(GitDeploy, cls).__new__(cls, *args,
                                                           **kwargs)

            # Call config
            cls.__instance._configure(**kwargs)

            log.debug('{0} :: Config - {1}'.format(__name__,
                      str(cls.__instance.config)))
        return cls.__instance

    def _configure(self, **kwargs):
        self.config = configure(**kwargs)

    def _parse_remote(self, args):
        """
        Parse git deploy remote/branch from command line args
        """
        if hasattr(args, 'ordered_args') and len(args.ordered_args) >= 3:
            remote = str(args.ordered_args[DEFAULT_REMOTE_ARG_IDX])
            branch = str(args.ordered_args[DEFAULT_BRANCH_ARG_IDX])
        else:
            remote = DEFAULT_REMOTE
            branch = DEFAULT_BRANCH

        return remote, branch

    @property
    def locker(self):
        return self._locker

    def start(self, _):
        """
            * write a lock file
        """

        # Create lock file - check if it already exists
        if self._locker.check_lock():
            raise GitDeployError(message=exit_codes[2])

        self._locker.add_lock()

        logline = 'STARTING git deploy.'
        self.deploy_log.log('user(' + self.config['user.name'] +
                            ') ' + logline)
        return 0

    def abort(self, _):
        """
            * reset state back to start tag
            * remove lock file
        """

        logline = 'ABORTING git deploy'
        log.info(__name__ + ' :: ' + logline)
        self.deploy_log.log('user(' + self.config['user.name'] +
                            ') ' + logline)
        self.deploy_log.log_archive()

        # Remove lock file
        self._locker.remove_lock()
        return 0

    def sync(self, args):
        """
            * add a sync tag
            * write a .deploy file with the tag information
            * call a sync hook with the prefix (repo) and tag info
        """

        if not self._locker.check_lock():
            raise GitDeployError(message=exit_codes[30], exit_code=30)

        remote, branch = self._parse_remote(args)

        kwargs = {
            'author': GitMethods()._make_author(),
            'tag': GitMethods()._make_tag('sync'),
            'remote': remote,
            'branch': branch,
            'force': args.force,
            'env': args.env,
            'dryrun': args.dryrun,
            'default': args.default,
            'release': args.release,
        }

        for key, value in self.config.iteritems():
            kwargs[key] = value

        return self._sync(kwargs)

    def _sync(self, kwargs):
        """
        This method makes calls to specialized drivers to perform the deploy.

            * Check for sync script
            * default sync if one is not specified
        """

        if kwargs['dryrun']:
            logline = 'SYNC -> dryrun.'
            log.info(__name__ + ' :: ' + logline)
            DeployDriverDryRun().sync(kwargs)

        else:
            logline = 'SYNC - calling default sync.'
            log.info(__name__ + ' :: ' + logline)
            self.deploy_log.log('user(' + self.config['user.name'] +
                                ') ' + logline)

            DeployDriverDefault().sync(kwargs)

            # Clean-up
            self.deploy_log.log_archive()
            if self._locker.check_lock():
                self._locker.remove_lock()

        logline = 'SYNC successful!'
        self.deploy_log.log('user(' + self.config['user.name'] +
                            ') ' + logline)
        return 0

    def revert(self, args):
        """
            * write a lock file
            * reset to last or specified tag
            * call sync hook with the prefix (repo) and tag info
        """

        if not self._locker.check_lock():
            raise GitDeployError(message=exit_codes[30])

        # Extract tag on which to revert
        tag = ''
        if hasattr(args, 'tag'):
            tag = args.tag

        if not hasattr(args, 'tag') or not tag:
            # revert to previous to current tag
            repo_tags = GitMethods()._get_deploy_tags()
            if len(repo_tags) >= 2:
                tag = repo_tags[-2]
            else:
                raise GitDeployError(message=exit_codes[36], exit_code=36)

            logline = 'REVERT -> no tag specified, using: \'{0}\''.format(tag)
            log.info(__name__ + ' :: ' + logline)
            self.deploy_log.log('user(' + self.config['user.name'] +
                                ') ' + logline)

        #
        # Rollback to tag:
        #
        #   1. get a commit list
        #   2. perform no-commit reverts
        #   3. commit
        #

        logline = 'REVERT -> Attempting to revert to tag: \'{0}\''.format(tag)
        log.info(__name__ + ' :: ' + logline)
        self.deploy_log.log('user(' + self.config['user.name'] +
                            ') ' + logline)

        tag_commit_sha = GitMethods()._get_commit_sha_for_tag(tag)
        commit_sha = None
        for commit_sha in GitMethods()._git_commit_list():
            if commit_sha == tag_commit_sha:
                break
            GitMethods()._git_revert(commit_sha)

        # Ensure the commit tag was matched
        if commit_sha != tag_commit_sha or not commit_sha:
            GitMethods()._dulwich_reset_to_tag()
            raise GitDeployError(message=exit_codes[35], exit_code=35)
        GitMethods()._dulwich_commit(GitMethods()._make_author(),
                                     message='Rollback to {0}.'.format(tag))

        logline = 'REVERT -> Reverted to tag: \'{0}\', call "git deploy ' \
                  'sync" to persist'.format(tag)
        log.info(__name__ + ' :: ' + logline)
        self.deploy_log.log('user(' + self.config['user.name'] +
                            ') ' + logline)

        if args.auto_sync:
            return self._sync(args)

        return 0

    def finish(self):
        """
        * Remove lock file
        """
        if self._locker.check_lock():
            self._locker.remove_lock()

    def show_tag(self, _):
        """
            * display latest deploy tag
        """
        # Get latest "sync" tag - sets self._tag
        print GitMethods()._get_latest_deploy_tag()
        return 0

    def log_deploys(self, args):
        """
            * show last x deploys
        """
        # Get number of deploy tags to emit
        try:
            num_tags = args.count
        except NameError:
            raise GitDeployError(message=exit_codes[10], exit_code=10)

        tags = GitMethods()._get_deploy_tags()

        if num_tags <= len(tags):
            tags = tags[:num_tags]

        for tag in tags:
            print tag
        return 0

    def diff(self, _):
        """
            * show a git diff of the last deploy and it's previous deploy
        """

        tags = GitMethods()._get_deploy_tags()

        # Check the return code & whether at least two sync tags were
        # returned
        if len(tags) < 2:
            raise GitDeployError(message=exit_codes[7], exit_code=7)

        # Get the associated commit hashes for those tags
        sha_1 = GitMethods()._get_commit_sha_for_tag(tags[0])
        sha_2 = GitMethods()._get_commit_sha_for_tag(tags[1])

        # Produce the diff
        lines = GitMethods()._git_diff(sha_1, sha_2)
        for line in lines:
            print line

        return 0

    def dummy(self, args):
        """
        dummy method to test the entry point.
        """
        log.info(__name__ + " :: CLI ars -> {0}".format(args))
        log.info(__name__ + " :: Passive call to the CLI.")
