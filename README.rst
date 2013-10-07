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
