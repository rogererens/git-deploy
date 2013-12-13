"""
Git methods
"""

__date__ = '2013-12-13'
__license__ = 'GPL v2.0 (or later)'

import os
import stat
import subprocess

from re import search
from time import time
from collections import OrderedDict

from dulwich import index
from dulwich.repo import Repo
from dulwich.objects import Tag, Commit, parse_timezone
from dulwich.diff_tree import tree_changes
from dulwich.client import get_transport_and_path

from config import log, exit_codes


class GitMethodsError(Exception):
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


class GitMethods(object):

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
        return cls.__instance

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
            raise GitMethodsError(message=exit_codes[8], exit_code=8)

    def _dulwich_tag(self, path, tag, author, message=DEFAULT_TAG_MSG):
        """
        Creates a tag in git via dulwich calls:

        Parameters:
            tag - string :: "<project>-[start|sync]-<timestamp>"
            author - string :: "Your Name <your.email@example.com>"
        """

        # Open the repo
        _repo = Repo(path)

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

    def _dulwich_reset_to_tag(self, path, tag=None):
        """
        Resets the HEAD to the commit
        """
        _repo = Repo(path)

        if not tag:
            sha = _repo.head()
        else:
            sha = self._get_commit_sha_for_tag(tag)

        try:
            _repo.refs['HEAD'] = sha
        except AttributeError:
            raise GitMethodsError(message=exit_codes[7], exit_code=7)

    def _dulwich_stage_all(self, path):
        """
        Stage modified files in the repo
        """
        _repo = Repo(path)

        # Iterate through files, those modified will be staged
        for elem in os.walk(path):
            relative_path = elem[0].split('./')[-1]
            if not search(r'\.git', elem[0]):
                files = [relative_path + '/' +
                         filename for filename in elem[2]]
                log.info(__name__ + ' :: Staging - {0}'.format(files))
                _repo.stage(files)

    def _dulwich_commit(self, path, author, message=DEFAULT_COMMIT_MSG):
        """
        Commit staged files in the repo
        """
        _repo = Repo(path)
        commit_id = _repo.do_commit(message, committer=author)

        if not _repo.head() == commit_id:
            raise GitMethodsError(message=exit_codes[14], exit_code=14)

    def _dulwich_status(self, path):
        """
        Return the git status
        """
        _repo = Repo(path)
        index = _repo.open_index()
        return list(tree_changes(_repo, index.commit(_repo.object_store),
                                 _repo['HEAD'].tree))

    def _dulwich_get_tags(self, path):
        """
        Get all tags & correspondin commit shas
        """
        _repo = Repo(path)
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

    def _dulwich_push(self, path, git_url, branch):
        """
        Remote push with dulwich via dulwich.client
        """

        # Open the repo
        _repo = Repo(path)

        # Get the client and path
        client, path = get_transport_and_path(git_url)

        def update_refs(refs):
            new_refs = _repo.get_refs()
            new_refs['refs/remotes/origin/' + branch] = new_refs['HEAD']
            del new_refs['HEAD']
            return new_refs

        client.send_pack(path, update_refs,
                         _repo.object_store.generate_pack_contents)

    def _dulwich_pull(self, path, git_url):
        """ Pull from remote via dulwich.client """

        # Open the repo
        _repo = Repo(path)

        client, path = get_transport_and_path(git_url)
        remote_refs = client.fetch(path, _repo)
        _repo['HEAD'] = remote_refs['refs/heads/master']

        self._dulwich_checkout(_repo)

    def _dulwich_checkout(self, _repo):
        """ Perform 'git checkout .' - syncs staged changes """

        indexfile = _repo.index_path()
        tree = _repo["HEAD"].tree
        index.build_index_from_tree(_repo.path, indexfile,
                                    _repo.object_store, tree)