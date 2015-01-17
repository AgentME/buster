Buster
======

Super simple, Totally awesome, Brute force **static site generator for**
`Ghost <http://ghost.org>`__.

Start with a clean, no commits Github repository.

*Generate Static Pages. Preview. Deploy to Github Pages.*

Warning! This project is a hack. It's not official. But it works for me.

The interface
-------------

``setup [--gh-repo=<repo-url>]``

      Creates a GIT repository inside ``static/`` directory.

``generate [--domain=<local-address>] [--dir=<path>] [--target=<remote-address>] [--replace-all=<true|false>]``

      Generates static pages from locally running Ghost instance.

``preview``

      Preview what's generated on ``localhost:9000``.

``deploy``

      Commits and deploys changes static files to Github repository.

``add-domain <domain-name>``

      Adds CNAME file with custom domain name as required by Github
Pages.

Buster assumes you have ``static/`` folder in your current directory (or
creates one during ``setup`` command). You can specify custom directory
path using ``[--dir=<path>]`` option to any of the above commands.

The ``[--replace-all=<true|false>]`` option switches between replacing
all urls buster can find, or only ``href`` attributes in ``a`` tags.

The ``[--target=<remote-address>]`` option let's you choose the target
domain and root directory of the generated site. This is especially
needed for the RSS/Atom feed that would otherwise point to ``--domain``.
The option provides an alternative to changing your blog URL in Ghost's
config.js (see below).

Don't forget to change your blog URL in config.js in Ghost.


The Installation
----------------

Installing Buster is easy with pip:

    $ pip install buster

You'll then have the wonderful ``buster`` command available.

You could also clone the source and use the ``buster.py`` file directly.

Requirements
------------

-  wget: Use ``brew install wget`` to install wget on your Mac.
   Available by default on most linux distributions.

-  git: Use ``brew install git`` to install git on your Mac.
   ``sudo apt-get install git`` on ubuntu/debian

The following python packages would be installed automatically when
installed via ``pip``:

-  `docopt <https://github.com/docopt/docopt>`__: Creates beautiful
   command line interfaces *easily*.
-  `GitPython <https://github.com/gitpython-developers/GitPython>`__:
   Python interface for GIT.
   `BeautifulSoup4 <http://www.crummy.com/software/BeautifulSoup/>`__:
   Painlessly parses and creates (x)HTML(5)
   `lxml <https://github.com/lxml/lxml/>`__: XML/HTML processor.

Example
_______

Generate a static version of your ghost blog with all links replaces via
``buster generate --domain=http://localhost:2368 --target=https://foo.com --replace-all=yes``

Ghost. What?
------------

`Ghost <http://ghost.org/features/>`__ is a beautifully designed,
completely customisable and completely `Open
Source <https://github.com/TryGhost/Ghost>`__ **Blogging Platform**. If
you haven't tried it out yet, check it out. You'll love it.

The Ghost Foundation is not-for-profit organization funding open source
software and trying to completely change the world of online publishing.
Consider `donating to Ghost <http://ghost.org/about/donate/>`__.

Buster?
~~~~~~~

Inspired by THE GhostBusters.

.. figure:: http://upload.wikimedia.org/wikipedia/en/c/c7/Ghostbusters_cover.png
   :alt: Ghost Buster Movie Poster

   Ghost Buster Movie

Contributing
------------

Checkout the existing
`issues <https://github.com/axitkhurana/buster/issues>`__ or create a
new one. Pull requests welcome!

--------------

*Made with* `jugaad <http://en.wikipedia.org/wiki/Jugaad>`__ *in*
`Dilli <http://en.wikipedia.org/wiki/Delhi>`__.
