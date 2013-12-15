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
import stat
import dulwich
import dulwich.walk
import subprocess

from re import search
from datetime import datetime

from dulwich.repo import Repo

from utils import ssh_command_target
from git_methods import GitMethods
from drivers.driver import DeployDriverDefault, DeployDriverHook
from config import log, configure, exit_codes, \
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


def remove_readonly(fn, path, excinfo):
    """
    Modifies path to writable for recursive path removal.
        e.g. shutil.rmtree(path, onerror=remove_readonly)
    """
    if fn is os.rmdir:
        os.chmod(path, stat.S_IWRITE)
        os.rmdir(path)
    elif fn is os.remove:
        os.chmod(path, stat.S_IWRITE)
        os.remove(path)


class GitDeploy(object):

    # Pattern for git-deploy tags
    TAG_PATTERN = r'[a-zA-Z]*-[0-9]{8}-[0-9]{6}'

    # Module level attribute for tagging datetime format
    DATE_TIME_TAG_FORMAT = '%Y%m%d-%H%M%S'

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

        # Stores tag state
        self._tag = None

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(GitDeploy, cls).__new__(cls, *args,
                                                           **kwargs)

            # Call config
            cls.__instance._configure(**kwargs)

            log.info('{0} :: Config - {1}'.format(__name__,
                     str(cls.__instance.config)))
        return cls.__instance

    def _configure(self, **kwargs):
        self.config = configure(**kwargs)

    def _check_lock(self):
        """ Returns boolean flag on lock file existence """
        cmd = "ls {0}{1}{2}".format(
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())

        # log.debug('{0} :: Executing - "{1}"'.format(__name__, cmd))
        log.info('{0} :: Checking for lock file at {1}.'.format(
            __name__, self.config['target']))
        ret = ssh_command_target(
            cmd,
            self.config['target'],
            self.config['user.name'],
            self.config['deploy.key_path'],
            )

        # Pull the lock file handle from
        try:
            file_handle = ret['stdout'][0].split('/')[-1].strip()
        except (IndexError, ValueError):
            log.info('{0} :: No lock file exists.'.format(
                __name__, self.config['target']))
            return False

        if file_handle == self._get_lock_file_name():
            log.info('{0} :: {1} has lock.'.format(
                __name__, self.config['user.name']))
            return True
        else:
            log.info('{0} :: Another user has lock.'.format(
                __name__, ))
            return False

    def _get_lock_file_name(self):
        return self.LOCK_FILE_HANDLE + '-' + self.config['user']

    def _create_lock(self):
        """
        Create a lock file

        Write the user name to the lock file in the dploy directory.
        """
        log.info('{0} :: SSH Lock create.'.format(__name__))

        cmd = "touch {0}{1}{2}".format(
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())
        ssh_command_target(
            cmd,
            self.config['target'],
            self.config['user.name'],
            self.config['deploy.key_path']
            )

    def _remove_lock(self):
        """ Remove the lock file """
        cmd = "rm {0}{1}{2}".format(
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())
        ssh_command_target(
            cmd,
            self.config['target'],
            self.config['user.name'],
            self.config['deploy.key_path'],
        )

    def _get_latest_deploy_tag(self):
        """
        Returns the latest tag containing 'sync'
        Sets self._tag to tag string
        """
        return self._get_deploy_tags()[-1]

    def _get_deploy_tags(self):
        """
        Returns the all deploy tags.
        """
        # 1. Pull last 'num_tags' sync tags
        # 2. Filter only matched deploy tags
        tags = GitMethods()._dulwich_get_tags(self.config['top_dir']).keys()
        f = lambda x: search(self.config['repo_name'] + '-sync-', x)
        return filter(f, tags)

    def _make_tag(self, tag_type):
        timestamp = datetime.now().strftime(self.DATE_TIME_TAG_FORMAT)
        return '{0}-{1}-{2}'.format(self.config['repo_name'], tag_type,
                                    timestamp)

    def _make_author(self):
        return '{0} <{1}>'.format(self.config['user.name'],
                                  self.config['user.email'])

    def _git_commit_list(self):
        """
        Generate an in-order list of commits
        """
        _repo = Repo(self.config['top_dir'])

        commits = []
        for entry in _repo.get_walker(order=dulwich.walk.ORDER_DATE):
            commits.append(entry.commit.id)

        return commits

    def _git_revert(self, commit_sha):
        """
        Perform a no-commit revert
        """
        cmd = 'git revert --no-commit {0}'.format(commit_sha)
        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.communicate()

        if proc.returncode != 0:
            raise GitDeployError(message=exit_codes[33], exit_code=33)

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

    def start(self, _):
        """
            * write a lock file
        """

        # Create lock file - check if it already exists
        if self._check_lock():
            raise GitDeployError(message=exit_codes[2])

        self._create_lock()

        return 0

    def abort(self, _):
        """
            * reset state back to start tag
            * remove lock file
        """

        # Get the commit hash of the current tag
        try:
            commit_sha = GitMethods()._get_commit_sha_for_tag(self._tag)
        except GitDeployError:
            # No current tag
            commit_sha = None

        # 1. hard reset the index to the desired tree
        # 2. move the branch pointer back to the previous HEAD
        # 3. commit revert
        # @TODO replace with dulwich

        if commit_sha:
            if subprocess.call("git reset --hard {0}".
                               format(commit_sha).split()):
                raise GitDeployError(message=exit_codes[5], exit_code=5)
            if subprocess.call("git reset --soft HEAD@{1}".split()):
                raise GitDeployError(message=exit_codes[5], exit_code=5)
            if subprocess.call("git commit -m 'Revert to {0}'".
                               format(commit_sha).split()):
                raise GitDeployError(message=exit_codes[5], exit_code=5)

        # Remove lock file
        self._remove_lock()
        return 0

    def sync(self, args):
        """
            * add a sync tag
            * write a .deploy file with the tag information
            * call a sync hook with the prefix (repo) and tag info
        """
        if not self._check_lock():
            raise GitDeployError(message=exit_codes[30], exit_code=30)

        tag = self._make_tag('sync')
        GitMethods()._dulwich_tag(self.config['top_dir'], tag,
                                  self._make_author())

        remote, branch = self._parse_remote(args)

        kwargs = {
            'author': self._make_author(),
            'remote': remote,
            'branch': branch,
            'tag,': tag,
            'sync_script': self.config['sync_script'],
            'repo_name': self.config['repo_name'],
            'client_path': self.config['client_path'],
            'hook_dir': self.config['hook_dir'],
            'target_path': self.config['path'],
            'force': args.force,
            'target_url': self.config['target'],
            'user': self.config['user.name'],
            'key_path': self.config['deploy.key_path']
        }

        return self._sync(args.sync, kwargs)

    def _sync(self, sync_script, kwargs):
        """
        This method makes calls to specialized drivers to perform the deploy.

            * Check for sync script
            * default sync if one is not specified
        """

        if sync_script:
            DeployDriverHook().sync(kwargs)
        else:
            DeployDriverDefault().sync(kwargs)

        # Clean-up
        if self._check_lock():
            self._remove_lock()

        return 0

    def revert(self, args):
        """
            * write a lock file
            * reset to last or specified tag
            * call sync hook with the prefix (repo) and tag info
        """

        if not self._check_lock():
            raise GitDeployError(message=exit_codes[30])

        # This will be the tag on the revert commit
        revert_tag = self._make_tag('revert')

        # Extract tag on which to revert
        if hasattr(args, 'tag'):
            tag = args.tag
        else:
            # revert to previous to current tag
            repo_tags = self._get_deploy_tags()
            if len(repo_tags) >= 2:
                tag = repo_tags[-2]
            else:
                raise GitDeployError(message=exit_codes[36], exit_code=36)

        # Ensure tag to revert to was set
        if tag == '':
            raise GitDeployError(message=exit_codes[13], exit_code=13)

        #
        # Rollback to tag:
        #
        #   1. get a commit list
        #   2. perform no-commit reverts
        #   3. commit
        #

        log.info(__name__ + ' :: revert - Attempting to revert to tag: {0}'.
                 format(tag))

        tag_commit_sha = GitMethods()._get_commit_sha_for_tag(tag)
        commit_sha = None
        for commit_sha in self._git_commit_list():
            if commit_sha == tag_commit_sha:
                break
            self._git_revert(commit_sha)

        # Ensure the commit tag was matched
        if commit_sha != tag_commit_sha or not commit_sha:
            GitMethods()._dulwich_reset_to_tag(self.config['top_dir'])
            raise GitDeployError(message=exit_codes[35], exit_code=35)
        GitMethods()._dulwich_commit(self.config['top_dir'],
                                     self._make_author(),
                                     message='Rollback to {0}.'.format(tag))

        log.info(__name__ + ' :: revert - Reverted to tag: "{0}", '
                            'call "git deploy sync" to persist'.format(tag))

        if args.auto_sync:
            return self._sync(revert_tag, args.force)

        return 0

    def finish(self):
        """
        * Remove lock file
        """
        if self._check_lock():
            self._remove_lock()

    def show_tag(self, _):
        """
            * display latest deploy tag
        """
        # Get latest "sync" tag - sets self._tag
        print self._get_latest_deploy_tag()
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

        tags = self._get_deploy_tags()

        if num_tags <= len(tags):
            tags = tags[:num_tags]

        for tag in tags:
            print tag
        return 0

    def diff(self, _):
        """
            * show a git diff of the last deploy and it's previous deploy
        """

        tags = self._get_deploy_tags()

        # Check the return code & whether at least two sync tags were
        # returned
        if len(tags) < 2:
            raise GitDeployError(message=exit_codes[7], exit_code=7)

        # Get the associated commit hashes for those tags
        sha_1 = GitMethods()._get_commit_sha_for_tag(tags[0])
        sha_2 = GitMethods()._get_commit_sha_for_tag(tags[1])

        # Produce the diff
        # @TODO replace with dulwich
        proc = subprocess.Popen("git diff {0} {1}".format(sha_2, sha_1).
                                split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        lines = proc.communicate()[0].split('\n')

        if not proc.returncode:
            for line in lines:
                print line
        else:
            raise GitDeployError(message=exit_codes[6], exit_code=6)
        return 0

    def dummy(self, args):
        """
        dummy method to test the entry point.
        """
        log.info(__name__ + " :: CLI ars -> {0}".format(args))
        log.info(__name__ + " :: Passive call to the CLI.")
