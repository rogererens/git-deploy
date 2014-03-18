git-deploy
==========

This project is based on the original implementation located at: https://github.com/git-deploy/git-deploy

We would like to thank the following people for their hard work and contributions to the original work:
@avar, @demerphq, @atomicstack, @b10m, @kristov, @mfjordvald, @rgs, @gugod, @ojacobson, @moltar, @dgryski and @guest20


It is a tool to manage using git as a deployment management tool implemented in Python and utilizing the dulwich [1]
project for native git functionality in Python.

Git-deploy implements the front end of the deployment system while hooks give the user flexibility in the lower level
details of the deploy.  This client uses git to manage the state of your repository and deployment and assumes that on
sync the hooks ensure that the target is made consistent with the client (see default.sync) however, the user is free to
add their own deployment flow and environment options (see examples below).

[1] https://github.com/jelmer/dulwich


Usage
-----

Basic usage involves cloning the remote working repo to the deploy target and all client nodes.  When
a client is ready to deploy 'start' is invoked to obtain a lock on the remote and 'sync' is called to
push changes to the target.  On completion the lock is removed.

To start a new deployment, navigate to the working repo, issue a 'start' command:

    $ git deploy start [opts]

At this point you are free to make commits to the project and when ready for deployment issue 
a 'sync' command - or simply 'sync' if you're work is already complete but, be sure to rebase
your local clone:

    $ git deploy sync [opts]

The process may be aborted at any point with an 'abort' command:

    $ git deploy abort [opts]

You can rollback to a tag with the revert call:

    $ git deploy revert [-t <tag_name>] [opts]

If no tag is supplied the rollback uses the most recent tag.  The default is to only commit the rollback locally
however, by suppling the "-a" option for auto-sync the rollback automatically syncs also:

    $ git deploy revert [-t <tag_name>] [opts]


Setup
-----

The following example illustrates how git-deploy can be configured and used for a single client and target.  For this
example the client host and target host will be referred to as *client.realm.org* and *target.realm.org* respectively.
The home path on the client and target for our sample project is */home/me/project/* and */var/www/html/sample.com/*
respectively.  It is assumed that the git remote is configured for your project and for this example the remote alias is
*origin* and the remote branch is *master*.


**CLIENT SETUP**

The client is any working machine from which deployments may be initiated.  On *client.realm.org* clone git deploy, local
install, configure settings and initialize:

    $ git clone git@github.com:Git-Tools/git-deploy.git

    ...

    $ cd git-deploy
    $ sudo pip install -e .

    ...

Next configure the client instance with git config by assigning the following settings in *scripts/git-deploy.ini*:

    [deploy]
        target=target.realm.org
        path=/home/me/project/
        user=me
        hook-dir=.git/deploy/hooks/
        tag-prefix=sample.com
        remote=origin
        branch=master
        client-path=/home/me/project/
        key-path=/home/me/.ssh/id_rsa
        test-repo-path=/tmp/test_repo/
    [system]
        run_root=/usr/bin/

Once you have defined settings in *git-deploy.ini* call *init.py* to set the got config

    $ sudo ./scripts/init_gd


**TARGET SETUP**

On *target.realm.org* there is no need to clone and install git-deploy but here the deploy hooks will need to be
created.  There is a default hook in *git-deploy/default-hooks/default-target-pull.py* that should be copied to
*target.realm.org:/var/www/html/sample.com/.git/deploy/hooks/*.  This is a basic hook that will pull the changes
pushed from the client instance on sync.


**USING GIT DEPLOY**

First initialize a new repository on your client:

    $ mkdir me.com
    $ cd me.com
    $ git init
    $ git remote add origin git@github.com:wikimedia/me.com.git
    $ git push origin master

On the target you only need to ensure that *path* in config exists and is configured as a git repo for your project.

*Start* & *Sync*:

Ensure that the client is correctly synced to the remote by issuing a git pull or rebase.  Then you can issue a
a start command to write the lock file to the target to begin the deployment.

    $ cd me.com
    $ touch new_file
    $ git add new_file
    $ git commit -m "add - my new file"
    $ git pull --rebase origin master

At this point you are ready to enter the deployment process:

    client.realm.org:me.com me$ git deploy start

    <perform any testing or add any other commits as necessary you've locked the remote at this point>

    client.realm.org:me.com me$ git deploy sync

Once you sync a the specified hooks will be invoked from the client and the target and a tag is written to the
repository on the latest commit of the deploy. If the default push and pull hooks are used the client will simply
push its changes to the remote and the target will pull in the new changes.  Deployment tags have the form
*<repo>-sync-<date>-<time>*.

Finally, you can also do a dryrun on the sync:

    $ git deploy sync -d

*Abort*

At times it is necessary to exit the deploy cycle prematurely.  For instance, consider the following:

    $ git deploy start
    $ git commit bad_change -m "add - some buggy code."

Suddenly, you realize that your change introduced a bug after entering the deloy process.  Rather than syncing the bad
code and then rolling back (next section) we can simply abort the deploy:

    $ git deploy abort
    $ git reset --soft HEAD^

    ... continue with your local changes ...

Now you have released deploy to other clients without infecting the code base with your buggy code.


*Rollback*

If you accidentally deploy some code that needs to be rolled back the *revert* command can be very helpful here.  You
can rollback to previous deploy states by utilizing deploy tags.  To view the old tags:

    $ git tag

Now to rollback to a previous deploy call *git revert* with the appropriate tag:

    $ git deploy start
    $ git deploy revert <tag>


Deploy Hooks
------------

This behaviour mimics that found in https://github.com/git-deploy/git-deploy#deploy-hooks &
https://github.com/git-deploy/git-deploy#writing-deploy-hooks.

The hooking system can be used to execute user defined actions in the deploy process.


**Writing Hooks**

This system is based around a sync model where a sync is the process by which the deploy target is made consistent with
a calling client.  There are two phases that define the behaviour around deployment, pre/post-sync.

The pre-deploy framework is expected to reside in the $GIT_WORK_DIR/deploy directory (i.e. the deploy directory of the
repository that's being rolled out). This directory has the following tree:

    $GIT_WORK_DIR/deploy/                   # deploy directory
                        /apps/              # Directory per application + 'common'
                             /common/       # deploy scripts that apply to all apps
                             /$app/         # deploy scripts for a specific $app
                        /sync/              # sync
                             /$app.sync

The $app in deploy/{apps,sync}/$app is the server prefix that you'd see in the rollout tag. E.g. A company might have
multiple environments which they roll out, for instance "sheep", "cows" and "goats". Here is a practical example of the
deployment hooks that might be used in the sheep environment:

    $ tree deploy/apps/{sheep,common}/ deploy/sync/
    deploy/apps/sheep/
    |-- post-sync.010_httpd_configtest.sh
    |-- post-sync.020_restart_httpd.sh
    |-- pre-sync.010_nobranch_rollout.sh
    |-- pre-sync.020_check_that_we_are_in_the_load_balancer.pl
    |-- pre-sync.021_take_us_out_of_the_load_balancer.pl
    `-- pre-sync.022_check_that_we_are_not_in_the_load_balancer.pl -> pre-pull.020_check_that_we_are_in_the_load_balancer.pl
    deploy/apps/common/
    |-- pre-sync.001_setup_affiliate_symlink.pl
    `-- pre-sync.002_check_permissions.pl
    deploy/sync/
    |-- sheep.sync

All the hooks in deploy/apps are prefixed by a phase in which git-deploy will execute them (e.g. pre-sync just before a sync).

During these phases git-deploy will glob in all the deploy/apps/{common,$app}/$phase.* hooks and execute them in sort order, first
the common hooks and then the $app specific hooks. Note that the hooks MUST have their executable bit set.


**Calling Environments**

To call an environment based deploy use the -e option:

    $ git deploy sync -e $ENV


Deploy Logging
--------------

Git deploy maintains a deploy log on the target's deploy root path.  The logs can be found under:

    ${DEPLOY_ROOT}/logs/git-deploy.log (archive)
    ${DEPLOY_ROOT}/logs/git-deploy-active.log (active)

The active log stores logging from any currently active deploys and is flush-appended to the archive log on
completion of a deploy.  There is currently no default log rotation implemented on the target in git-deploy
so this would have to be added manually if desired.


Examples
--------

**Reverting to a tag**

This example illustrates how to rollback a deploy to an earlier tag.

In the directory of the client repository check Git history:

    richrushbay-lm:test_sartoris rfaulk$ git log

    commit 779a07774dd5a7baf8dc86657cbfc491264ff970
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sun Dec 8 23:28:50 2013 -0800

        test

    commit 1ab80a78fc1e89ae6f8872282f96f5f42677b843
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sat Nov 16 18:31:26 2013 -0800

        test git-deploy 20131116_0.file.

    commit 12311863e111a266c4c1c513da45a39ed3e8cdd5
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sat Nov 2 19:42:58 2013 -0700

        Initial commit.

Next, take a look at the existing sync tags:

    richrushbay-lm:test_sartoris rfaulk$ git tag

    sartoris-sync-20131220-000105
    sartoris-sync-20131220-012354
    sartoris-sync-20131220-013503

Let's start the deploy:

    richrushbay-lm:test_sartoris rfaulk$ git deploy start

    Dec-20 01:53:00 DEBUG    git-deploy is ready to run
    Dec-20 01:53:00 INFO     git_deploy.git_deploy :: Config - {'deploy.test_repo': '/tmp/test/', 'deploy.key_path': '/Users/rfaulk/.ssh/id_rsa', 'target': 'stat1.wikimedia.org', 'top_dir': '/Users/rfaulk/Projects/test_sartoris', 'user.name': 'rfaulk', 'user.email': 'rfaulk@yahoo-inc.com', 'deploy.remote_url': 'git@github.com:rfaulkner/test_sartoris.git', 'hook_dir': '.git/deploy/hooks/', 'client_path': '/Users/rfaulk/Projects/test_sartoris/', 'sync_dir': '.git/deploy/hooks//sync', 'path': '/home/rfaulk/test_sartoris/', 'repo_name': 'sartoris', 'deploy_file': '/Users/rfaulk/Projects/test_sartoris/.git/.deploy', 'user': 'rfaulk'}
    Dec-20 01:53:00 INFO     git_deploy.git_deploy :: Checking for lock file at stat1.wikimedia.org.
    Dec-20 01:53:01 INFO     git_deploy.git_deploy :: No lock file exists.
    Dec-20 01:53:01 INFO     git_deploy.git_deploy :: SSH Lock create.

Next call the revert action - a tag can be explicitly supplied, but in this example it isn't and the rollback applies to the
previous sync tag:

    richrushbay-lm:test_sartoris rfaulk$ git deploy revert

    Dec-20 01:53:13 DEBUG    git-deploy is ready to run
    Dec-20 01:53:13 INFO     git_deploy.git_deploy :: Config - {'deploy.test_repo': '/tmp/test/', 'deploy.key_path': '/Users/rfaulk/.ssh/id_rsa', 'target': 'stat1.wikimedia.org', 'top_dir': '/Users/rfaulk/Projects/test_sartoris', 'user.name': 'rfaulk', 'user.email': 'rfaulk@yahoo-inc.com', 'deploy.remote_url': 'git@github.com:rfaulkner/test_sartoris.git', 'hook_dir': '.git/deploy/hooks/', 'client_path': '/Users/rfaulk/Projects/test_sartoris/', 'sync_dir': '.git/deploy/hooks//sync', 'path': '/home/rfaulk/test_sartoris/', 'repo_name': 'sartoris', 'deploy_file': '/Users/rfaulk/Projects/test_sartoris/.git/.deploy', 'user': 'rfaulk'}
    Dec-20 01:53:13 INFO     git_deploy.git_deploy :: Checking for lock file at stat1.wikimedia.org.
    Dec-20 01:53:15 INFO     git_deploy.git_deploy :: rfaulk has lock.
    Dec-20 01:53:15 INFO     git_deploy.git_deploy :: REVERT -> no tag specified, using: 'sartoris-sync-20131220-012354'
    Dec-20 01:53:15 INFO     git_deploy.git_deploy :: REVERT -> Attempting to revert to tag: 'sartoris-sync-20131220-012354'
    Dec-20 01:53:15 INFO     git_deploy.git_deploy :: REVERT -> Reverted to tag: 'sartoris-sync-20131220-012354', call "git deploy sync" to persist

And sync the changes:

    richrushbay-lm:test_sartoris rfaulk$ git deploy sync

    Dec-20 01:53:49 DEBUG    git-deploy is ready to run
    Dec-20 01:53:49 INFO     git_deploy.git_deploy :: Config - {'deploy.test_repo': '/tmp/test/', 'deploy.key_path': '/Users/rfaulk/.ssh/id_rsa', 'target': 'stat1.wikimedia.org', 'top_dir': '/Users/rfaulk/Projects/test_sartoris', 'user.name': 'rfaulk', 'user.email': 'rfaulk@yahoo-inc.com', 'deploy.remote_url': 'git@github.com:rfaulkner/test_sartoris.git', 'hook_dir': '.git/deploy/hooks/', 'client_path': '/Users/rfaulk/Projects/test_sartoris/', 'sync_dir': '.git/deploy/hooks//sync', 'path': '/home/rfaulk/test_sartoris/', 'repo_name': 'sartoris', 'deploy_file': '/Users/rfaulk/Projects/test_sartoris/.git/.deploy', 'user': 'rfaulk'}
    Dec-20 01:53:49 INFO     git_deploy.git_deploy :: Checking for lock file at stat1.wikimedia.org.
    Dec-20 01:53:51 INFO     git_deploy.git_deploy :: rfaulk has lock.
    Dec-20 01:53:51 INFO     git_deploy.git_deploy :: SYNC - tag local
    Dec-20 01:53:51 INFO     git_deploy.git_deploy :: SYNC - calling default sync.
    Dec-20 01:53:51 INFO     git_deploy.drivers.driver :: Calling default sync - pushing changes ...
    Dec-20 01:53:53 INFO     PUSH ->
    Dec-20 01:53:53 INFO     git_deploy.drivers.driver :: Calling default sync - pulling to target
    Dec-20 01:53:56 INFO     PULL -> Updating 779a077..38f42d3; Fast-forward
    Dec-20 01:53:56 INFO     git_deploy.git_deploy :: Checking for lock file at stat1.wikimedia.org.
    Dec-20 01:53:57 INFO     git_deploy.git_deploy :: rfaulk has lock.
    Dec-20 01:53:57 INFO     git_deploy.git_deploy :: SSH Lock destroy.

We're done, check the git history, you should see a rollback commit.  This is persisted to the remote repo and the target host:

    richrushbay-lm:test_sartoris rfaulk$ git log

    commit 38f42d3be6831c16b475786f3016bcc588499e56
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Fri Dec 20 09:53:15 2013 +0000

        Rollback to sartoris-sync-20131220-012354.

    commit 779a07774dd5a7baf8dc86657cbfc491264ff970
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sun Dec 8 23:28:50 2013 -0800

        test

    commit 1ab80a78fc1e89ae6f8872282f96f5f42677b843
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sat Nov 16 18:31:26 2013 -0800

        test git-deploy 20131116_0.file.

    commit 12311863e111a266c4c1c513da45a39ed3e8cdd5
    Author: rfaulk <rfaulk@yahoo-inc.com>
    Date:   Sat Nov 2 19:42:58 2013 -0700

        Initial commit.

Finally, note the new sync tag for the rollback:

    richrushbay-lm:test_sartoris rfaulk$ git tag

    sartoris-sync-20131220-000105
    sartoris-sync-20131220-012354
    sartoris-sync-20131220-013503
    sartoris-sync-20131220-015351


**Dryrun of the default**


In this example we have the following deploy tree:

    $ tree deploy/apps/{prod,common}/ deploy/sync/
    deploy/apps/prod/
    |-- post-sync.010_test.sh
    |-- post-sync.020_test.sh
    |-- pre-sync.010_test.sh
    |-- pre-sync.020_test.sh
    deploy/apps/common/
    |-- pre-sync.010_test.sh
    |-- post-sync.010_test.sh
    deploy/sync/
    |-- prod.sync
    |-- default.sync

To execute the dryrun on the default note that any app specific hooks are ignored:

    $ git deploy start

    Jan-14 23:19:26 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 23:19:27 INFO     git_deploy.lockers.locker :: No lock file exists.
    Jan-14 23:19:27 INFO     git_deploy.lockers.locker :: Creating lock file at stat1.wikimedia.org:/home/rfaulk/test_sartoris/.git/deploy//lock-rfaulk.lock.

    $ git deploy sync -d

    Jan-14 23:19:32 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 23:19:34 INFO     git_deploy.lockers.locker :: rfaulk has lock.
    Jan-14 23:19:34 INFO     git_deploy.git_deploy :: SYNC -> dryrun.
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: DRYRUN SYNC
    Jan-14 23:19:34 INFO     --> TAG 'sartoris-sync-20140114-231934'
    Jan-14 23:19:34 INFO     --> AUTHOR 'rfaulk <rfaulk@yahoo-inc.com>'
    Jan-14 23:19:34 INFO     --> REMOTE 'origin'
    Jan-14 23:19:34 INFO     --> BRANCH 'master'
    Jan-14 23:19:34 INFO     DUMPING DEPLOY SCRIPTS IN ORDER OF EXECUTION.
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: Calling pre-sync common: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/pre-sync.010_test.sh' ON PHASE 'pre-sync'

        #!/bin/bash
        echo "common pre-sync"

    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/" ...
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync" ...
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync/default.sync' ON PHASE 'default'

        #!/usr/bin/python
        # -*- coding: utf-8 -*-

        """

        Default sync script that performs push from client.  The expected ops
        are the following:

            cd $GIT_DEPLOY_HOME
            /usr/bin/git push origin master
            /usr/bin/git push --tags

        """

        import sys
        import logging

        from git_deploy.git_deploy import GitMethods
        from git_deploy.utils import ssh_command_target

        log_format = "%(asctime)s %(levelname)-8s %(message)s"
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(fmt=log_format,
                             datefmt='%b-%d %H:%M:%S'))


        def main():

            # Dulwich push
            remote = GitMethods().config['deploy.remote_url']
            logging.info(__name__ + ' :: Default sync, pushing to \'{0}\''.format(
                remote))
            GitMethods()._dulwich_push(remote, 'master')

            # git pull on remote
            target_path = GitMethods().config['path']
            cmd = "git --git-dir={0}/.git --work-tree={0} pull origin master".format(
                target_path)
            target = GitMethods().config['target']
            user = GitMethods().config['user.name']
            key_path = GitMethods().config['deploy.key_path']

            logging.info(__name__ + ' :: Default sync, pulling '
                                    'changes to \'{0}\''.format(target))
            ssh_command_target(cmd, target, user, key_path)


        def cli():
            sys.exit(main())

        if __name__ == "__main__":  # pragma: nocover
            cli()

    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/" ...
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/post-sync.010_test.sh' ON PHASE 'post-sync'

        #!/bin/bash
        echo "common post-sync"

    Jan-14 23:19:34 INFO     git_deploy.drivers.driver :: DRYRUN SYNC COMPLETE


**Dryrun and sync to an environment**


In this example we have a set of dummy hooks:

    $ tree deploy/apps/{prod,common}/ deploy/sync/
    deploy/apps/prod/
    |-- post-sync.010_test.sh
    |-- post-sync.020_test.sh
    |-- pre-sync.010_test.sh
    |-- pre-sync.020_test.sh
    deploy/apps/common/
    |-- pre-sync.010_test.sh
    |-- post-sync.010_test.sh
    deploy/sync/
    |-- prod.sync
    |-- default.sync

These hooks just do some simple echoing, a dryrun will illustrate how the hooking system executes through the phases of
deploy.  In fact, if you like, you can setup separate environments to serve as different phases themselves.  Note,
that as we're specifiying environment the default.sync is ignored.  Without further ado:

    $ git deploy start

    Jan-14 00:11:17 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 00:11:18 INFO     git_deploy.lockers.locker :: No lock file exists.
    Jan-14 00:11:18 INFO     git_deploy.lockers.locker :: Creating lock file at stat1.wikimedia.org:/home/rfaulk/test_sartoris/.git/deploy//lock-rfaulk.lock.

Do the dryrun:

    $ git deploy sync -d -e prod

    Jan-14 23:06:31 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 23:06:32 INFO     git_deploy.lockers.locker :: rfaulk has lock.
    Jan-14 23:06:32 INFO     git_deploy.git_deploy :: SYNC -> dryrun.
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: DRYRUN SYNC
    Jan-14 23:06:32 INFO     --> TAG 'sartoris-sync-20140114-230632'
    Jan-14 23:06:32 INFO     --> AUTHOR 'rfaulk <rfaulk@yahoo-inc.com>'
    Jan-14 23:06:32 INFO     --> REMOTE 'origin'
    Jan-14 23:06:32 INFO     --> BRANCH 'master'
    Jan-14 23:06:32 INFO     DUMPING DEPLOY SCRIPTS IN ORDER OF EXECUTION.
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: Calling pre-sync common: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/pre-sync.010_test.sh' ON PHASE 'pre-sync'

        #!/bin/bash
        echo "common pre-sync"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod" ...
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.010_test.sh' ON PHASE 'pre-sync'

        #!/bin/bash
        echo "prod pre-sync 1"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.020_test.sh' ON PHASE 'pre-sync'

        #!/bin/bash
        echo "prodn pre-sync 2"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync" ...
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync/prod.sync' ON PHASE 'prod'

        #!/bin/bash
        echo prod.sync

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod" ...
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.010_test.sh' ON PHASE 'post-sync'

        #!/bin/bash
        echo "prod post-sync 1"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.020_test.sh' ON PHASE 'post-sync'

        #!/bin/bash
        echo "prod post-sync 2"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/post-sync.010_test.sh' ON PHASE 'post-sync'

        #!/bin/bash
        echo "common post-sync"

    Jan-14 23:06:32 INFO     git_deploy.drivers.driver :: DRYRUN SYNC COMPLETE

Finally, let's execute the dummy sync:

    $ git deploy sync -e prod

    Jan-14 23:07:38 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 23:07:40 INFO     git_deploy.lockers.locker :: rfaulk has lock.
    Jan-14 23:07:40 INFO     git_deploy.git_deploy :: SYNC - calling default sync.
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: Calling pre-sync common: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/pre-sync.010_test.sh' ON PHASE 'pre-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/pre-sync.010_test.sh OUT -> common pre-sync

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod" ...
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.010_test.sh' ON PHASE 'pre-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.010_test.sh OUT -> prod pre-sync 1

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.020_test.sh' ON PHASE 'pre-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/pre-sync.020_test.sh OUT -> prodn pre-sync 2

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: Calling pre-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync" ...
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/sync/prod.sync' ON PHASE 'prod'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/sync/prod.sync OUT -> prod.sync

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod" ...
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.010_test.sh' ON PHASE 'post-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.010_test.sh OUT -> prod post-sync 1

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.020_test.sh' ON PHASE 'post-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/prod/post-sync.020_test.sh OUT -> prod post-sync 2

    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: Calling post-sync app: "/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common" ...
    Jan-14 23:07:40 INFO     git_deploy.drivers.driver :: CALLING '/Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/post-sync.010_test.sh' ON PHASE 'post-sync'
    Jan-14 23:07:40 INFO     /Users/rfaulk/Projects/test_sartoris//.git/deploy/apps/common/post-sync.010_test.sh OUT -> common post-sync

    Jan-14 23:07:40 INFO     git_deploy.lockers.locker :: Checking for lock file at stat1.wikimedia.org.
    Jan-14 23:07:41 INFO     git_deploy.lockers.locker :: rfaulk has lock.
    Jan-14 23:07:41 INFO     git_deploy.lockers.locker :: SSH Lock destroy.
    Jan-14 23:07:41 INFO     git_deploy.lockers.locker :: Removing lock file at stat1.wikimedia.org:/home/rfaulk/test_sartoris/.git/deploy//lock-rfaulk.lock.


Development
-----------

Pull requests welcome!  If you love Python and git this may be the perfect project for you.  All source is PEP8
compliant Python 2.7 compatible.  Please drop in tests where possible for new additions.

Patrick Reilly (patrick.reilly at gmail dot com) and Ryan Faulkner (bobs.ur.uncle at gmail dot com).
