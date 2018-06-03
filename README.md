Buster
======

Static site generator for Ghost <http://ghost.org>.

Usage
-----

    $ python3 ./buster/buster.py generate [--path output/dir] [source-url] [target-url]`

Generates static pages from a running Ghost instance. The pages will be saved
in the static/ directory unless you override this with the `--path` option.

The source URL should be equal to the public URL configured in Ghost's config
(or the "url" environment variable given to the Ghost Docker container), which
should not have a trailing slash.

The source URL will be rewritten in links, meta tags, etc, as the target URL.

    $ python3 ./buster/buster.py preview [--path [output/dir]]`

Serve the output directory on http://localhost:9000.

    $ python3 ./buster/buster.py [command] -h

Outputs additional usage information for a command. Some commands such as
`generate` have more optional parameters that you can see the documentation of
by doing this.

    $ python3 -h

Outputs top-level help

Installation
------------

Clone the repository, and run

    $ pip3 install -r requirements.txt

You must also have wget installed on your system.

Example
-------

Generate a static version of your ghost blog via
`python3 ./buster/buster.py generate http://localhost:2368 https://foo.com --path /output/dir`

Docker
------

The docker image [agentme/buster](https://hub.docker.com/r/agentme/buster/)
runs a script which automatically runs Buster every time Ghost's database is
modified.

The source url should be passed as the `GHOST_ADDRESS` environment variable,
and the target url should be passed as the `STATIC_ADDRESS` environment
variable. An HTTP password may be supplied through the `BUSTER_PASSWORD`
environment variable. (The HTTP user "buster" will be used if a password is
given.)

The Buster docker container should have the same volume mounted as read-only
to it that Ghost has mounted at `/var/lib/ghost/content`, and the Buster
docker container should have a second volume mounted at `/var/static_ghost`.
The Buster docker container will write the static files under
`/var/static_ghost/current/`. The `/var/static_ghost/current/` directory will
be a symlink which is automatically and atomically updated after each time
Buster exports the site to static files, so a web server pointed at
`/var/static_ghost/current/` will never see files from an incomplete export.

About
-----

This project is a fork of https://github.com/axitkhurana/buster with the
git-related functionality removed and many bugs fixed, including supporting
RSS feeds and text encoding correctly.
