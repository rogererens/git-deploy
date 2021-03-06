"""
Git methods
"""

__date__ = '2013-12-13'
__license__ = 'GPL v2.0 (or later)'

import sys
import os
import subprocess
from datetime import datetime

from re import search
from collections import OrderedDict

from dulwich import walk
from dulwich import index
from dulwich import porcelain
from dulwich.repo import Repo
from dulwich.diff_tree import tree_changes
from dulwich.porcelain import push, pull, commit, tag

from config import log, exit_codes, configure


class GitMethodsError(Exception):
    """ Basic exception class for UserMetric types """
    def __init__(self, message="Git deploy error.", exit_code=1):
        Exception.__init__(self, message)
        self._exit_code = int(exit_code)

    @property
    def exit_code(self):
        return self._exit_code


class GitMethods(object):

    # Module level attribute for tagging datetime format
    DATE_TIME_TAG_FORMAT = '%Y%m%d-%H%M%S'

    # Default tag message
    DEFAULT_TAG_MSG = 'GitDeploy Tag.'

    # Default tag message
    DEFAULT_COMMIT_MSG = 'GitDeploy Commit'

    # class instance
    __instance = None

    def __init__(self, *args, **kwargs):
        """ Initialize class instance """
        self.__class__.__instance = self

    def __new__(cls, *args, **kwargs):
        """ This class is Singleton, return only one instance """
        if not cls.__instance:
            cls.__instance = super(GitMethods, cls).__new__(cls, *args,
                                                            **kwargs)
            # Call config
            cls.__instance._configure(**kwargs)

        return cls.__instance

    def _configure(self, **kwargs):
        self.config = configure(**kwargs)

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
        tags = GitMethods()._dulwich_get_tags().keys()
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
        for entry in _repo.get_walker(order=walk.ORDER_DATE):
            commits.append(entry.commit.id)

        return commits

    def _git_diff(self, sha_1, sha_2):
        """Produce the diff between sha1 & sha2

        :param sha_1: commit sha of "before" state
        :param sha_2: commit sha of "before" state
        """
        _repo = Repo(self.config['top_dir'])

        c_old = _repo.get_object(sha_1)
        c_new = _repo.get_object(sha_1)

        # default writes to stdout
        try:
            porcelain.diff_tree(_repo, c_old.tree, c_new.tree)
        except:
            raise GitMethodsError(message=exit_codes[6], exit_code=6)

    def _git_revert(self, commit_sha):
        """Perform a no-commit revert

        :param commit_sha: commit sha to revert to
        """

        # TODO - replace native git
        cmd = 'git revert --no-commit {0}'.format(commit_sha)
        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        proc.communicate()

        if proc.returncode != 0:
            raise GitMethodsError(message=exit_codes[33], exit_code=33)

    def _get_commit_sha_for_tag(self, tag):
        """Obtain the commit sha of an associated tag

        :param tag: git tag to match to commit sha
        """
        for repo_tag, commit_obj in self._dulwich_get_tags():
            if tag == repo_tag:
                return commit_obj.id

        raise GitMethodsError(message=exit_codes[8], exit_code=8)

    def _dulwich_tag(self, tag_text, author, message=DEFAULT_TAG_MSG):
        """
        Creates a tag in git via dulwich calls:

        :param tag_text:    tag string
        :param author:      author string
        :param message:     message string
        """
        tag(self.config['top_dir'], tag_text, author, message)

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
            raise GitMethodsError(message=exit_codes[7], exit_code=7)

    def _dulwich_stage_all(self):
        """
        Stage modified files in the repo
        """
        _repo = Repo(self.config['top_dir'])

        # Iterate through files, those modified will be staged
        for elem in os.walk(self.config['top_dir']):
            relative_path = elem[0].split('./')[-1]
            if not search(r'\.git', elem[0]):
                files = [relative_path + '/' +
                         filename for filename in elem[2]]
                log.info(__name__ + ' :: Staging - {0}'.format(files))
                _repo.stage(files)

    def _dulwich_commit(self, author, message=DEFAULT_COMMIT_MSG):
        """
        Commit staged files in the repo
        """
        commit(self.config['top_dir'], message=message, author=author)

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
        ordered_tags = {}
        # Get the commit hashes associated with the tags
        for tag, tag_commit in tags.items():
            if tag not in ordered_tags:
                ordered_tags[tag] = _repo.object_store.peel_sha(tag_commit)
        # Sort by commit_time, then by tag name, as multiple tags can have
        # the same commit_time for their commits
        ordered_tags = OrderedDict(sorted(ordered_tags.items(),
                                          key=lambda t: (t[1].commit_time, t)))
        return ordered_tags

    def _dulwich_push(self, remote_location, refs_path):
        """Remote push with dulwich.porcelain

        :param repo : Path to repository
        :param remote_location: Location of the remote
        :param refs_path: relative path to the refs to push to remote
        """
        push(self.config['top_dir'], remote_location, refs_path)

    def _dulwich_pull(self, remote_location, refs_path, errstream=sys.stderr):
        """ Pull from remote via dulwich.porcelain

        :param repo: Path to repository
        :param remote_location: Location of the remote
        :param refs_path: relative path to the fetched refs
        """
        pull(self.config['top_dir'], remote_location, refs_path)

    def _dulwich_checkout(self, _repo):
        """ Perform 'git checkout .' - syncs staged changes """

        indexfile = _repo.index_path()
        tree = _repo["HEAD"].tree
        index.build_index_from_tree(_repo.path, indexfile,
                                    _repo.object_store, tree)
