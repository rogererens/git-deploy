#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""

`This`_ is a tool to manage using git as a deployment management tool

.. _This: https://gerrit.wikimedia.org/r/gitweb?p=sartoris.git

"""

__license__ = """\
Copyright (c) 2012-2013 Wikimedia Foundation <info@wikimedia.org>

Permission to use, copy, modify, and distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.\
"""

import argparse
import os
import stat
import sys
from re import search
import subprocess
from dulwich.repo import Repo
from dulwich.objects import Tag, Commit, parse_timezone
from datetime import datetime
import json
from time import time
from config import set_log, log, configure, exit_codes


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


def parseargs():
    """Parse command line arguments.

    Returns *args*, the list of arguments left over after processing.

    """
    parser = argparse.ArgumentParser(
        description="This script performs ",
        epilog="",
        conflict_handler="resolve",
        usage="sartoris [-q --quiet] [-s --silent] [-v --verbose] [method]"
    )

    parser.allow_interspersed_args = False

    defaults = {
        "quiet": 0,
        "silent": False,
        "verbose": 0,
    }

    # Global options.
    parser.add_argument("method")
    parser.add_argument("-c", "--count",
                        default=1, type=int,
                        help="number of tags to log")
    parser.add_argument("-q", "--quiet",
                        default=defaults["quiet"], action="count",
                        help="decrease the logging verbosity")
    parser.add_argument("-s", "--silent",
                        default=defaults["silent"], action="store_true",
                        help="silence the logger")
    parser.add_argument("-v", "--verbose",
                        default=defaults["verbose"], action="count",
                        help="increase the logging verbosity")
    parser.add_argument("-f", "--force",
                        action="store_true",
                        help="force the action, bypass sanity checks.")

    args = parser.parse_args()
    return args


class Sartoris(object):

    # Module level attribute for tagging datetime format
    DATE_TIME_TAG_FORMAT = '%Y%m%d-%H%M%S'

    # Name of deployment directory
    DEPLOY_DIR = '.git/deploy/'

    # Name of lock file
    LOCK_FILE_HANDLE = 'lock'

    # Default tag message
    DEFAULT_TAG_MSG = 'Sartoris Tag.'

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
            cls.__instance._configure()

            log.info('{0} :: Config - {1}'.format(__name__,
                     str(cls.__instance.config)))
        return cls.__instance

    def _configure(self):
        self.config = configure()

    def _get_current_lock_user(self):
        """
        Pulls the expected lock user from lock file
        """
        cmd = "ssh {0}@{1} cat {2}/{3}/{4}".format(
            self.config['user'],
            self.config['target'],
            self.config['path'],
            self.DEPLOY_DIR,
            self.LOCK_FILE_HANDLE)

        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        return proc.communicate()[0].strip('\n')

    def _check_lock(self):
        """ Returns boolean flag on lock file existence """
        cmd = "ssh {0}@{1} ls {2}/{3}/{4}".format(
            self.config['user'],
            self.config['target'],
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())

        log.debug('{0} :: Executing - {1}'.format(__name__, cmd))
        proc = subprocess.Popen(cmd.split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        result = proc.communicate()[0].split('\n')
        log.debug('{0} :: Result of {1} - {2}'.format(__name__, cmd, result))

        if not proc.returncode:

            # Pull the lock file handle from
            try:
                file_handle = result[0].split('/')[-1].strip()
            except (IndexError, ValueError):
                log.debug('{0} :: Could not extract '
                          'the lock file name.'.format(__name__))
                return False

            if file_handle == self._get_lock_file_name():
                return True
            else:
                return False
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

        os.system("ssh {0}@{1} touch {2}/{3}/{4}".format(
            self.config['user'],
            self.config['target'],
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name()))

    def _remove_lock(self):
        """ Remove the lock file """
        cmd = "ssh {0}@{1} rm {2}/{3}/{4}".format(
            self.config['user'],
            self.config['target'],
            self.config['path'],
            self.DEPLOY_DIR,
            self._get_lock_file_name())
        log.info('{0} :: Executing - {1}'.format(__name__, cmd))
        os.system(cmd)

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
        """ Returns the latest tag containing 'sync'
            Sets self._tag to tag string
        """
        proc = subprocess.Popen("git tag".split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        self._tag = None
        for line_out in proc.communicate()[0].split('\n'):
            if search(r'sync', line_out):
                self._tag = line_out

        if proc.returncode:
            raise SartorisError(message=exit_codes[8], exit_code=8)
        elif not self._tag:
            raise SartorisError(message=exit_codes[8], exit_code=8)
        return 0

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

    def start(self, args):
        """
            * write a lock file
            * add a start tag
        """
        # @TODO use dulwich package implement git functionality rather
        #       than shell commands - http://www.samba.org/~jelmer/dulwich/

        # Create lock file - check if it already exists
        # @TODO catch exceptions for any os callable attributes
        if self._check_lock():
            raise SartorisError(message=exit_codes[2])

        self._create_lock()

        return 0

    def abort(self, args):
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

    def sync(self, args, no_deps=False, force=False):
        """
            * add a sync tag
            * write a .deploy file with the tag information
            * call a sync hook with the prefix (repo) and tag info
        """
        #TODO: do git calls in dulwich, rather than shelling out
        if not self._check_lock():
            exit_code = 30
            log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
            return exit_code
        repo_name = self.config['repo_name']
        _tag = "{0}-sync-{1}".format(repo_name,
                                     datetime.now().strftime(
                                         self.DATE_TIME_TAG_FORMAT))
        proc = subprocess.Popen(['/usr/bin/git', 'tag', '-a', _tag,
                                 '-m', '"test sync"'])
        proc.communicate()

        if proc.returncode != 0:
            exit_code = 31
            log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
            return exit_code

        # Write .deploy file
        try:
            deploy_file = open(self.config['deploy_file'], 'w')
            deploy_file.write(json.dumps({'repo': repo_name, 'tag': _tag}))
            deploy_file.close()
        except OSError:
            exit_code = 32
            log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
            return exit_code

        return self._sync(_tag, args.force)

    def _sync(self, tag, force):
        repo_name = self.config['repo_name']
        sync_script = '{0}/{1}.sync'.format(self.config["sync_dir"], repo_name)

        #TODO: use a pluggable sync system rather than shelling out
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
            timestamp = datetime.now().strftime(self.DATE_TIME_TAG_FORMAT)

            _tag = '{0}-{1}'.format(self.config['user'], timestamp)
            _author = '{0} <{1}>'.format(self.config['user.name'],
                                         self.config['user.email'])
            try:
                self._dulwich_tag(_tag, _author)
            except Exception as e:
                logging.error(str(e))
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

        proc = subprocess.Popen(['{0}{1}default-client-push.py'.format(
            self.config['client-path'], self.config['hook-dir']
        ), self.config['remote'], self.config['branch']])
        proc_out = proc.communicate()[0]
        log.info(proc_out)

        # TODO - push tags

        #
        # Call deploy hook on remote
        #
        #   {% PATH %}/.git/deploy/hooks/default-client-pull origin master
        #
        log.info('{0} :: Calling default sync - '
                 'pulling to target'.format(__name__))
        proc = subprocess.Popen(['{0}{1}default-client-pull.py'.format(
            self.config['path'], self.config['hook-dir']
        ), self.config['remote'], self.config['branch']])
        proc_out = proc.communicate()[0]
        log.info(proc_out)

        return

    def resync(self, args):
        """
            * write a lock file
            * call sync hook with the prefix (repo) and tag info
            * remove lock file
        """
        if self._check_lock():
            exit_code = 2
            log.error('{0} :: {1}'.format(__name__, exit_codes[exit_code]))
            return exit_code
        self._create_lock()
        repo_name = self.config['repo_name']
        try:
            deploy_file = open(self.config['deploy_file'], 'r')
            deploy_info = deploy_file.read()
            deploy_info = json.loads(deploy_info)
        except OSError:
            exit_code = 50
            log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
            return exit_code
        return self._sync(repo_name, deploy_info["tag"])

    def revert(self, args):
        """
            * write a lock file
            * write previous deploy info into .deploy
            * call sync hook with the prefix (repo) and tag info
            * remove lock file
        """
        # Create lock file - check if it already exists
        # @TODO catch exceptions for any os callable attributes
        if self._check_lock():
            raise SartorisError(message=exit_codes[2])

        self._create_lock()
        repo_name = self.config['repo_name']

        # Get latest "sync" tag - sets self._tag
        self._get_latest_deploy_tag()

        # Write .deploy file
        try:
            deploy_file = open(self.config['deploy_file'], 'w')
            deploy_file.write(json.dumps({'repo': repo_name,
                                          'tag': self._tag}))
            deploy_file.close()
        except OSError:
            exit_code = 32
            log.error("{0} :: {1}".format(__name__, exit_codes[exit_code]))
            return exit_code

        # @TODO determine what to pass as arg 2
        self._sync(self._tag, args.force)

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

    def show_tag(self, args):
        """
            * display latest deploy tag
        """
        # Get latest "sync" tag - sets self._tag
        self._get_latest_deploy_tag()
        print self._tag
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

        # Get tags for project
        proc = subprocess.Popen("git tag".split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        # Pull last 'num_tags' sync tags
        # Reverse the tags since the later ones will appear further down
        tags = proc.communicate()[0].split('\n')
        tags.reverse()
        for tag in tags:
            if not num_tags:
                break
            if search(r'sync', tag):
                print tag
                num_tags -= 1
        return 0

    def diff(self, args):
        """
            * show a git diff of the last deploy and it's previous deploy
        """

        # Get the last two tags - assumes tagging on deployment only
        proc = subprocess.Popen("git tag".split(),
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,)

        # Get the last two tags
        sync_tags = filter(lambda x: search(r'sync', x),
                           proc.communicate()[0].split('\n'))

        # Check the return code & whether at least two sync tags were
        # returned
        if proc.returncode:
            raise SartorisError(message=exit_codes[6], exit_code=6)
        elif len(sync_tags) < 2:
            raise SartorisError(message=exit_codes[7], exit_code=7)

        # Get the associated commit hashes for those tags
        sha_1 = self._get_commit_sha_for_tag(sync_tags[0])
        sha_2 = self._get_commit_sha_for_tag(sync_tags[1])

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


def main(argv, out=None, err=None):
    """Main entry point.

    Returns a value that can be understood by :func:`sys.exit`.

    :param argv: a list of command line arguments, usually :data:`sys.argv`.
    :param out: stream to write messages; :data:`sys.stdout` if None.
    :param err: stream to write error messages; :data:`sys.stderr` if None.
    """
    if out is None:  # pragma: nocover
        out = sys.stdout
    if err is None:  # pragma: nocover
        err = sys.stderr
    args = parseargs()
    set_log(args, out, err)

    log.debug("Sartoris is ready to run")

    # Inline call to functionality - if Sartoris does not possess this
    #  attribute flag with logger
    if not args.method:
        print args.help
        return 3

    if hasattr(Sartoris(), args.method) and callable(getattr(Sartoris(),
                                                     args.method)):
        try:
            getattr(Sartoris(), args.method)(args)
        except SartorisError as e:
            log.error(e.message)
            return e.exit_code
    else:
        log.error(__name__ + ' :: No function called %(method)s.' % {
            'method': args.method})


def cli():
    sys.exit(main(sys.argv))

if __name__ == "__main__":  # pragma: nocover
    cli()
