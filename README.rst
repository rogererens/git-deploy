Sartoris
========

This is the Sartoris project.
It is a tool to manage using git as a deployment management tool

**Sartoris**

The project is named after a novel authored by William Faulkner entitled Sartoris, first published in 1929.
It portrays the decay of the Mississippi aristocracy following the social upheaval of the American Civil War.

This name was chosen because Ryan Faulkner is working on the project and we thought it would be funny.

- Published: 1929
- Author: William Faulkner
- Original language: English
- Preceded by: Mosquitoes
- Followed by: The Sound and the Fury
- Genre: Novel

Source: http://en.wikipedia.org/wiki/Sartoris


Client Configuration
--------------------

The client is any working machine from which deployments may be initiated.  To configure a client,
begin by cloning the repository to your client environment:

    $ git clone https://github.com/wikimedia/sartoris.git sartoris

Next, navigate to the root folder and install the package.

    $ sudo pip install -e .

Next, execute the initialization script, this will prepare the git config and copy the git deploy script.  Make sure that
the relevant values are set in sartoris.ini for your client/server-target beforehand (see below).

    $ sudo ./scripts/init.py

The .ini file defines the dependencies for the deploy section in your global .gitconfig:

    deploy.target {%target host%} # e.g. my.remotehost.com:8080 a.k.a deploy host

    deploy.path {%remote deploy path%}

    deploy.user {%authorized user on deploy target%}

    deploy.hook-dir .git/deploy/hooks/

    deploy.tag-prefix {%project name%}

    deploy.remote {%remote name%}

    deploy.branch {%deploy branch name%}

    deploy.client-path {%client path%}

Also ensure that the global git params user.name and user.email are defined.


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
free to write your own hooks however, simple default hooks have been provided in 'sartoris/default-hooks',
these can be copied to the hook folder in each client and target.


Example
-------

The following example illustrates how git-deploy can be configured and used for a single client and target.  For this
example the client host and target host will be referred to as *client.realm.org* and *target.realm.org* respectively.
The home path on the client and target for our sample project is */home/me/project/* and */var/www/html/sample.com/*
respectively.  It is assumed that the git remote is configured for your project and for this example the remote alias is
*origin* and the remote branch is *master*.

###Client Setup

On your client machine clone git deploy, local install, configure settings and initialize:

    $ git clone git@github.com:Git-Tools/git-deploy.git

        Cloning into 'git-deploy'...
        remote: Counting objects: 943, done.
        remote: Compressing objects: 100% (380/380), done.
        remote: Total 943 (delta 538), reused 936 (delta 531)
        Receiving objects: 100% (943/943), 153.47 KiB | 208 KiB/s, done.
        Resolving deltas: 100% (538/538), done.

    $ cd git-deploy
    $ sudo pip install -e .

        Obtaining file:///Users/rfaulkner/projects/git-deploy
          Running setup.py egg_info for package from file:///Users/rfaulkner/projects/git-deploy

            warning: no files found matching '*' under directory 'docs'
            no previously-included directories found matching 'docs/_build'
        Requirement already satisfied (use --upgrade to upgrade): dulwich in /Library/Python/2.7/site-packages (from sartoris==0.1-devdev-20131021)
        Requirement already satisfied (use --upgrade to upgrade): paramiko>=1.11.0 in /Library/Python/2.7/site-packages (from sartoris==0.1-devdev-20131021)
        Requirement already satisfied (use --upgrade to upgrade): pycrypto>=2.1,!=2.4 in /Library/Python/2.7/site-packages (from paramiko>=1.11.0->sartoris==0.1-devdev-20131021)
        Installing collected packages: git-deploy
          Running setup.py develop for git-deploy

            warning: no files found matching '*' under directory 'docs'
            no previously-included directories found matching 'docs/_build'
            Creating /Library/Python/2.7/site-packages/git-deploy.egg-link (link to .)
            sartoris 0.1-devdev-20131021 is already the active version in easy-install.pth
            Installing git-deploy script to /usr/local/bin

            Installed /Users/rfaulkner/projects/git-deploy
        Successfully installed git-deploy
        Cleaning up...

Next configure the client instance with git config by assigning the following settings:

    [deploy]
    target=target.realm.org
    path=/home/me/project/
    user=me
    hook-dir=.git/deploy/hooks/
    tag-prefix=sample.com
    remote=origin
    branch=master
    client-path=/home/me/project/
    [system]
    run_root=/usr/bin/


###Target Setup


###Using Hooks


###Using Git-Deploy




