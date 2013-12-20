git-deploy
==========

It is a tool to manage using git as a deployment management tool implemented in Python and utilizing the dulwich [1] project for native git functionality in Python.

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

Deploy Hooks
------------

In the working path of your local clone deploy hooks may be added to '.git/deploy/hooks'.  You are
free to write your own hooks however, simple default hooks have been provided in 'git-deploy/default-hooks',
these can be copied to the hook folder in each client and target.


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

First initialize a new repository on *client.realm.org*:

    client.realm.org:~ me$ mkdir me.com

    client.realm.org:~ me$ cd me.com

    client.realm.org:~ me$ git init

    client.realm.org:~ me$ git remote add origin git@github.com:wikimedia/me.com.git

    client.realm.org:~ me$ git push origin master

Next initialize the client repo by following the client setup above.  Subsequently, initialize the deploy target
on *target.realm.org* as indicated.

    target.realm.org:~ me$ cp ~/default-client-pull.py /var/www/html/sample.com/.git/deploy/hooks/

    target.realm.org:~ me$ chmod +x /var/www/html/sample.com/.git/deploy/hooks/default-client-pull.py


*Start* & *Sync*:

Ensure that the client is correctly synced to the remote by issuing a git pull or rebase.  Then you can issue a
a start command to write the lock file to the target to begin the deployment.

    client.realm.org:~ me$ cd me.com

    client.realm.org:me.com me$ touch new_file

    client.realm.org:me.com me$ git add new_file

    client.realm.org:me.com me$ git commit -m "add - my new file"

    client.realm.org:me.com me$ git pull --rebase origin master

At this point you are ready to enter the deployment process:

    client.realm.org:me.com me$ git deploy start

    <perform any testing or add any other commits as necessary you've locked the remote at this point>

    client.realm.org:me.com me$ git deploy sync

Once you sync a the specified hooks will be invoked from the client and the target and a tag is written to the
repository on the latest commit of the deploy. If the default push and pull hooks are used the client will simply
push its changes to the remote and the target will pull in the new changes.  Deployment tags have the form
*<repo>-sync-<date>-<time>*.


*Abort*

At times it is necessary to exit the deploy cycle prematurely.  For instance, consider the following:

    client.realm.org:me.com me$ git deploy start

    client.realm.org:me.com me$ git commit bad_change -m "add - some buggy code."

Suddenly, you realize that your change introduced a bug after entering the deloy process.  Rather than syncing the bad
code and then rolling back (next section) we can simply abort the deploy:

    client.realm.org:me.com me$ git deploy abort

    client.realm.org:me.com me$ git reset --soft HEAD^

    ... continue with your local changes ...

Now you have released deploy to other clients without infecting the code base with your buggy code.


*Rollback*

If you accidentally deploy some code that needs to be rolled back the *revert* command cn be very helpful here.  You
can rollback to previous deploy states by utilizing deploy tags.  To view the old tags:

    client.realm.org:me.com me$ git tag

Now to rollback to a previous deploy call *git revert* with the appropriate tag:

    client.realm.org:me.com me$ git deploy start

    client.realm.org:me.com me$ git deploy revert <tag>


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
    Dec-20 01:53:15 INFO     git_deploy.git_deploy :: REVERT -> no tag specified, using: ''
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