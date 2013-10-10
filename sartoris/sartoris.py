"""
This module defines the entities utilized to operate the git-deploy system
defined by the Sartoris project.
"""

__authors__ = {
    'Ryan Faulkner': 'bobs.ur.uncle@gmail.com',
    'Patrick Reilly': 'patrick.reilly@gmail.com',
    'Ryan Lane': 'rlane@wikimedia.org',
}
__date__ = '2013-09-08'
__license__ = 'GPL v2.0 (or later)'

import os
import stat
import paramiko
import socket
from re import search
import subprocess
from time import time
from datetime import datetime
from collections import OrderedDict

from dulwich.repo import Repo
from dulwich.objects import Tag, Commit, parse_timezone
from dulwich.diff_tree import tree_changes

from config import log, configure, exit_codes, DEFAULT_CLIENT_HOOK, \
    DEFAULT_TARGET_HOOK
from config_local import PKEY, PROJECT_HOME


class SartorisError(Exception):
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


class Sartoris(object):

    # Pattern for git-deploy tags
    TAG_PATTERN = r'[a-zA-Z]*-[0-9]{8}-[0-9]{6}'

    # Module level attribute for tagging datetime format
    DATE_TIME_TAG_FORMAT = '%Y%m%d-%H%M%S'

    # Name of deployment directory
    DEPLOY_DIR = '.git/deploy/'

    # Name of lock file
    LOCK_FILE_HANDLE = 'lock'

    # Default tag message
    DEFAULT_TAG_MSG = 'Sartoris Tag.'

    # Default tag message
    DEFAULT_COMMIT_MSG = 'Sartoris Commit'

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
            cls.__instance = super(Sartoris, cls).__new__(cls, *args, **kwargs)

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

        log.debug('{0} :: Executing - "{1}"'.format(__name__, cmd))
        ret = self.ssh_command_target(cmd)

        # Pull the lock file handle from
        try:
            file_handle = ret['stdout'][0].split('/')[-1].strip()
        except (IndexError, ValueError):
            log.debug('{0} :: Could not extract '
                      'the lock file name.'.format(__name__))
            return False

        if file_handle == self._get_lock_file_name():
            return True
        else:
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
        self.ssh_command_target(cmd)

    def _remove_lock(self):
        """ Remove the lock file """
        cmd = "rm {0}{1}{2}".format(
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())
        self.ssh_command_target(cmd)

    def _get_commit_sha_for_tag(self, tag):
        """ Obtain the commit sha of an associated tag
                e.g. `git rev-list $TAG | head -n 1` """
        # @TODO replace with dulwich

        cmd = "git rev-list {0}".format(tag)
        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        result = proc.communicate()[0].split('\n')

        if not proc.returncode and len(result) > 0:
            return result[0].strip()
        else:
            raise SartorisError(message=exit_codes[8], exit_code=8)

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
        tags = self._dulwich_get_tags().keys()
        f = lambda x: search(self.config['user'] + '-', x)
        return filter(f, tags)

    def _dulwich_tag(self, tag, author, message=DEFAULT_TAG_MSG):
        """
        Creates a tag in git via dulwich calls:

        Parameters:
            tag - string :: "<project>-[start|sync]-<timestamp>"
            author - string :: "Your Name <your.email@example.com>"
        """

        # Open the repo
        _repo = Repo(self.config['top_dir'])

        # Create the tag object
        tag_obj = Tag()
        tag_obj.tagger = author
        tag_obj.message = message
        tag_obj.name = tag
        tag_obj.object = (Commit, _repo.refs['HEAD'])
        tag_obj.tag_time = int(time())
        tag_obj.tag_timezone = parse_timezone('-0200')[0]

        # Add tag to the object store
        _repo.object_store.add_object(tag_obj)
        _repo['refs/tags/' + tag] = tag_obj.id

    def _dulwich_reset_to_tag(self, tag=None):
        """
        Resets the HEAD to the commit
        """
        _repo = Repo(self.config['top_dir'])

        if not tag:
            sha = _repo.head()
        else:
            sha = self._get_commit_sha_for_tag(tag)

        try:
            _repo.refs['HEAD'] = sha
        except AttributeError:
            raise SartorisError(message=exit_codes[7], exit_code=7)

    def _dulwich_stage_all(self):
        """
        Stage modified files in the repo
        """
        _repo = Repo(self.config['top_dir'])

        # Iterate through files, those modified will be staged
        for elem in os.walk(self.config['top_dir']):
            if not search(r'\.git', elem[0]):
                files = [(elem[0] + '/' + file).split(PROJECT_HOME)[-1]
                         for file in elem[2]]
                log.info(__name__ + ' :: Staging - {0}'.format(files))
                _repo.stage(files)

    def _dulwich_commit(self, author, message=DEFAULT_COMMIT_MSG):
        """
        Commit staged files in the repo
        """
        _repo = Repo(self.config['top_dir'])
        commit_id = _repo.do_commit(message, committer=author)

        if not _repo.head() == commit_id:
            raise SartorisError(message=exit_codes[14], exit_code=14)

    def _dulwich_status(self):
        """
        Return the git status
        """
        _repo = Repo(self.config['top_dir'])
        index = _repo.open_index()
        return list(tree_changes(_repo, index.commit(_repo.object_store),
                                 _repo['HEAD'].tree))

    def _dulwich_get_tags(self):
        """
        Get all tags & correspondin commit shas
        """
        _repo = Repo(self.config['top_dir'])
        tags = _repo.refs.as_dict("refs/tags")
        tag_keys = tags.keys()
        commits = [commit for _, commit in tags.iteritems()]

        # Reorder list by commit time
        # TODO - this is a non dulwich dependency, refactor this to
        # TODO (cont.) - use timestamps from the repo
        #
        ordered_tags = OrderedDict()

        for commit in self._git_commit_list():
            if commit in commits:
                index = commits.index(commit)
                ordered_tags[tag_keys[index]] = commit

        return ordered_tags

    def _make_tag(self):
        timestamp = datetime.now().strftime(self.DATE_TIME_TAG_FORMAT)
        return '{0}-{1}'.format(self.config['user'], timestamp)

    def _make_author(self):
        return '{0} <{1}>'.format(self.config['user.name'],
                                  self.config['user.email'])

    def _git_commit_list(self):
        """
        Generate an in-order list of commits
        """
        cmd = 'git log --pretty=oneline'
        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc_out = proc.communicate()

        if proc.returncode != 0:
            raise SartorisError(message=exit_codes[34], exit_code=34)

        commits = [i.split()[0] for i in proc_out[0][:-1].split('\n')]

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
            raise SartorisError(message=exit_codes[33], exit_code=33)

    def start(self, _):
        """
            * write a lock file
            * add a start tag
        """

        # Create lock file - check if it already exists
        if self._check_lock():
            raise SartorisError(message=exit_codes[2])

        self._create_lock()

        return 0

    def abort(self, _):
        """
            * reset state back to start tag
            * remove lock file
        """

        # Get the commit hash of the current tag
        try:
            commit_sha = self._get_commit_sha_for_tag(self._tag)
        except SartorisError:
            # No current tag
            commit_sha = None

        # 1. hard reset the index to the desired tree
        # 2. move the branch pointer back to the previous HEAD
        # 3. commit revert
        # @TODO replace with dulwich

        if commit_sha:
            if subprocess.call("git reset --hard {0}".
                               format(commit_sha).split()):
                raise SartorisError(message=exit_codes[5], exit_code=5)
            if subprocess.call("git reset --soft HEAD@{1}".split()):
                raise SartorisError(message=exit_codes[5], exit_code=5)
            if subprocess.call("git commit -m 'Revert to {0}'".
                               format(commit_sha).split()):
                raise SartorisError(message=exit_codes[5], exit_code=5)

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
            raise SartorisError(message=exit_codes[30], exit_code=30)

        tag = self._make_tag()

        return self._sync(tag, args.force)

    def _sync(self, tag, force):

        repo_name = self.config['repo_name']
        sync_script = '{0}/{1}.sync'.format(self.config["sync_dir"], repo_name)

        if os.path.exists(sync_script):
            log.info('{0} :: Calling sync script at {1}'.format(__name__,
                                                                sync_script))
            proc = subprocess.Popen([sync_script,
                                     '--repo="{0}"'.format(repo_name),
                                     '--tag="{0}"'.format(tag),
                                     '--force="{0}"'.format(force)])
            proc_out = proc.communicate()[0]
            log.info(proc_out)

            if proc.returncode != 0:
                exit_code = 40
                log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
                return exit_code
        else:
            # In absence of a sync script -- Tag the repo
            log.debug(__name__ + ' :: Calling default sync.')

            try:
                self._dulwich_tag(tag, self._make_author())
            except Exception as e:
                log.error(str(e))
                raise SartorisError(message=exit_codes[12], exit_code=12)

            self._default_sync()

        self._remove_lock()
        return 0

    def _default_sync(self):

        #
        # Call deploy hook on client
        #
        #   {% PATH %}/.git/deploy/hooks/default-client-push origin master
        #
        log.info('{0} :: Calling default sync - '
                 'pushing changes ... '.format(__name__))
        proc = subprocess.Popen(['{0}{1}{2}'.format(
            self.config['client_path'],
            self.config['hook_dir'],
            DEFAULT_CLIENT_HOOK),
            self.config['remote'],
            self.config['branch']],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        log.info('PUSH -> ' + '; '.join(
            filter(lambda x: x, proc.communicate())))

        #
        # Call deploy hook on remote
        #
        #   ssh user@target {% PATH %}/.git/deploy/hooks/default-client-pull \
        #       origin master
        #
        log.info('{0} :: Calling default sync - '
                 'pulling to target'.format(__name__))
        cmd = '{0}{1}{2} {3} {4}'.format(self.config['path'],
                                         self.config['hook_dir'],
                                         DEFAULT_TARGET_HOOK,
                                         self.config['remote'],
                                         self.config['branch'])
        ret = self.ssh_command_target(cmd)
        log.info('PULL -> ' + '; '.join(
            filter(lambda x: x, ret['stdout'])))

    def scp_file(self, source, target, port=22):
        """
        SCP files via paramiko.
        """

        # Socket connection to remote host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.config['target'], port))

        # Build a SSH transport
        t = paramiko.Transport(sock)
        t.start_client()

        rsa_key = paramiko.RSAKey.from_private_key_file(PKEY)
        t.auth_publickey(self.config['user.name'], rsa_key)

        # Start a scp channel
        scp_channel = t.open_session()

        f = file(source, 'rb')
        scp_channel.exec_command('scp -v -t %s\n'
                                 % '/'.join(target.split('/')[:-1]))
        scp_channel.send('C%s %d %s\n'
                         % (oct(os.stat(source).st_mode)[-4:],
                            os.stat(source)[6],
                            target.split('/')[-1]))
        scp_channel.sendall(f.read())

        # Cleanup
        f.close()
        scp_channel.close()
        t.close()
        sock.close()

    def ssh_command_target(self, cmd):
        """
        Talk to the target via SSHClient
        """

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            self.config['target'],
            username=self.config['user.name'],
            key_filename=PKEY)
        stdin, stdout, stderr = ssh.exec_command(cmd)

        stdout = [line.strip() for line in stdout.readlines()]
        stderr = [line.strip() for line in stderr.readlines()]

        ssh.close()

        return {
            'stdout': stdout,
            'stderr': stderr,
        }

    def revert(self, args):
        """
            * write a lock file
            * reset to last or specified tag
            * call sync hook with the prefix (repo) and tag info
        """

        if not self._check_lock():
            raise SartorisError(message=exit_codes[30])

        # This will be the tag on the revert commit
        revert_tag = self._make_tag()

        # Extract tag on which to revert
        if hasattr(args, 'tag'):
            tag = args.tag
        else:
            # revert to previous to current tag
            repo_tags = self._dulwich_get_tags()
            if len(repo_tags) >= 2:
                tag = repo_tags.keys()[-2]
            else:
                raise SartorisError(message=exit_codes[36], exit_code=36)

        # Ensure tag to revert to was set
        if tag == '':
            raise SartorisError(message=exit_codes[13], exit_code=13)

        #
        # Rollback to tag:
        #
        #   1. get a commit list
        #   2. perform no-commit reverts
        #   3. commit
        #

        log.info(__name__ + ' :: revert - Attempting to revert to tag: {0}'.
                 format(tag))

        tag_commit_sha = self._get_commit_sha_for_tag(tag)
        commit_sha = None
        for commit_sha in self._git_commit_list():
            if commit_sha == tag_commit_sha:
                break
            self._git_revert(commit_sha)

        # Ensure the commit tag was matched
        if commit_sha != tag_commit_sha or not commit_sha:
            self._dulwich_reset_to_tag()
            raise SartorisError(message=exit_codes[35], exit_code=35)
        self._dulwich_commit(self._make_author(),
                             message='Rollback to {0}.'.format(tag))

        log.info(__name__ + ' :: revert - Reverted to tag: "{0}", '
                            'call "git deploy sync" to persist'.format(tag))

        if args.auto_sync:
            return self._sync(revert_tag, args.force)

        return 0

    def release(self):
        """
        * tag a release and push to remote
        In this case you may want to perform the rollout yourself.
        """
        pass

    def finish(self):
        """
        Call after rolling out on 'release'
        """
        pass

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
            raise SartorisError(message=exit_codes[10], exit_code=10)

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
            raise SartorisError(message=exit_codes[7], exit_code=7)

        # Get the associated commit hashes for those tags
        sha_1 = self._get_commit_sha_for_tag(tags[0])
        sha_2 = self._get_commit_sha_for_tag(tags[1])

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
            raise SartorisError(message=exit_codes[6], exit_code=6)
        return 0
