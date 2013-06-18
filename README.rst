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

Usage
-----

First set the "hook-dir" and "tag-prefix" for the deploy section in your global .gitconfig:

	git config --global deploy.target {%target host%} # e.g. my.remotehost.com:8080 a.k.a deploy host

	git config --global deploy.path {%remote deploy path%}

	git config --global deploy.user {%authorized user on deploy target%}

	git config --global deploy.hook-dir .git/deploy/hooks

	git config --global deploy.tag-prefix {%project name%}

Next create the sartoris configuration file by first copying ./sartoris/config.py.example to 
./sartoris/config.py then setting the TEST_REPO and SARTORIS_HOME variables.  The TEST_REPO
should be defined in your /tmp folder while SARTORIS_HOME should point to the your local
Sartoris project home.

To start a new deployment issue a 'start' command:

	python {% SARTORIS_HOME %}/sartoris/sartoris.py start

At this point you are free to make commits to the project and when ready for deployment issue 
a 'sync' command:

	python {% SARTORIS_HOME %}/sartoris/sartoris.py sync

The process may be aborted at any point with an 'abort' command:

	python {% SARTORIS_HOME %}/sartoris/sartoris.py abort

