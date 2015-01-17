"""Ghost Buster. Static site generator for Ghost.

Usage:
  buster.py setup [--gh-repo=<repo-url>] [--dir=<path>]
  buster.py generate [--domain=<local-address>] [--dir=<path>] [--target=<remote-address>] [--replace-all=<true|false>]
  buster.py preview [--dir=<path>]
  buster.py deploy [--dir=<path>]
  buster.py add-domain <domain-name> [--dir=<path>]
  buster.py (-h | --help)
  buster.py --version

Options:
  -h --help                 Show this screen.
  --version                 Show version.
  --dir=<path>              Absolute path of local directory to store static pages.
  --domain=<local-address>  Address of local ghost installation [default: localhost:2368].
  --target=<remote-address> Address of target root URL (e.g. https://domain.com/path/to/root) [default: --domain]
  --replace-all=<yes|no>    Whether to only replace URLs found in a tags, or all occurences of --domain [default: no]
  --gh-repo=<repo-url>      URL of your gh-pages repository.
"""

import os
import re
import sys
import fnmatch
import shutil
import SocketServer
import SimpleHTTPServer
from docopt import docopt
from time import gmtime, strftime
from git import Repo
from bs4 import BeautifulSoup
from lxml import etree, html
from io import StringIO, BytesIO

def main():
    # TODO: arguments should be handled with argparse (https://docs.python.org/2/library/argparse.html)
    arguments = docopt(__doc__, version='0.1.3.bs4')
    if arguments['--dir'] is not None:
        static_path = arguments['--dir']
    else:
        static_path = os.path.join(os.getcwd(), 'static')
        
    # set default --domain to localhost:2368, as in the description above
    if arguments['--domain'] is not None:
        local_domain = arguments['--domain']
    else:
        local_domain = "http://localhost:2368"
        
    # make sure that --target is set as well
    # (this is needed for RSS, since otherwise urls in the feed resolve to the local_domain)
    if arguments['--target'] is not None:
        target_root = arguments['--target']
    else:
        target_root = local_domain
    
    # set scope for url replacement (i.e. only <a> tags or everything)
    if arguments['--replace-all'] == "yes":
        replace_all = True
    else:
        replace_all = False
    
    if arguments['generate']:
        command = ("wget "
                   "--recursive "             # follow links to download entire site
                   "--convert-links "         # make links relative
                   "--page-requisites "       # grab everything: css / inlined images
                   "--no-parent "             # don't go to parent level
                   "--directory-prefix {1} "  # download contents to static/ folder
                   "--no-host-directories "   # don't create domain named folder
                   "--restrict-file-name=unix "  # don't escape query string
                   "{0}").format(local_domain, static_path)
        os.system(command)

        
        # init list of renamed files
        files = list()

        # remove query string since Ghost 0.4
        file_regex = re.compile(r'.*?(\?.*)')
        for root, dirs, filenames in os.walk(static_path):
            for filename in filenames:
                if file_regex.match(filename):
                    newname = re.sub(r'\?.*', '', filename)
                    print "Rename", filename, "=>", newname
                    os.rename(os.path.join(root, filename), os.path.join(root, newname))
                    files.append(newname) # add new name to file-list
        
        # remove superfluous "index.html" from relative hyperlinks found in text
        abs_url_regex = re.compile(r'^(?:[a-z]+:)?//', flags=re.IGNORECASE)

        # form regex from file-list (i.e. all files, with stripped arguments from above)
        url_suffix_regex = re.compile(r'(' + "|".join(files) + r')(\?.*?(?=\"))', flags = re.IGNORECASE)

        def repl(m): # select regex matching group 
            print "---Removing", m.group(2), "from", m.group(1)
            return m.group(1)

        def fixAllUrls(data, parser, encoding):
            
            # step 1:
            # load HTML/XML in lxml
            if parser == "xml": # parser for XML that keeps CDATA elements (beautifulsoup doesn't)
                parser = etree.XMLParser(encoding=encoding, strip_cdata=False, resolve_entities=True)
                data = etree.XML(data, parser)
                # format the parsed xml for output (keep all non-ascii chars inside CDATA)
                data = etree.tostring(data, pretty_print=True, encoding=encoding)
            if parser == "lxml": # parser for HTML ("lenient" setting for html5)

                # the following should work, but spits out utf-8 numeric character references...

                # parser = etree.HTMLParser(encoding=encoding, strip_cdata=False)
                # if isinstance(data, str):
                #     data = unicode(data, encoding)
                # data = etree.parse(StringIO(data), parser)
                # data = html.tostring(data.getroot(), pretty_print=True, method="html")
                # data = u'<!DOCTYPE html>\n' + data
                
                # BeautifulSoup outputs html entities with formatter="html". lxml above should be faster
                data = BeautifulSoup(data, "html5lib").prettify(encoding,formatter="minimal")
                
            # step 2:
            # substitute all occurences of --domain (local_domain) argument with --target (target_root)
            data = re.sub(local_domain, target_root, data)

            # step 3:
            # remove URL arguments (e.g. query string) from renamed files
            # TODO: make it work with googlefonts
            data = url_suffix_regex.sub(repl, data)
            return data

        def fixUrls(data, parser, encoding):
            # Is this is a HTML document AND are we looking only for <a> tags?
            if parser == 'lxml' and not replace_all:
                soup = BeautifulSoup(data, parser) # TODO: replace beautifulsoup with lxml (still beats pyQuery, though)
                # adjust all href attributes of html-link elements
                for a in soup.findAll('a'):                                                 # for each <a> element
                    if not abs_url_regex.search(a['href']):                                 # that is not an absolute URL
                        new_href = re.sub(r'rss/index\.html$', 'rss/index.rss', a['href'])  # adjust href case 1
                        new_href = re.sub(r'/index\.html$', '/', new_href)                  # adjust href case 2,
                        print "\t", a['href'], "=>", new_href                               # tell about it,
                        a['href'] = a['href'].replace(a['href'], new_href)                  # perform replacement, and
                return soup.prettify(encoding,formatter="html") # return pretty utf-8 html with encoded html entities

            # Otherwise, fall through to fixAllUrls() for all other cases
            # (XML needs to always go through here AND we want to replace all URLs)
            return fixAllUrls(data, parser, encoding)

        # fix links in all html files
        for root, dirs, filenames in os.walk(static_path):
            for filename in fnmatch.filter(filenames, "*.html"):
                   filepath = os.path.join(root, filename)
                   parser = 'lxml'              # beautifulsoup parser selection (i.e. lxml)
                   if root.endswith("/rss"):    # rename rss index.html to index.rss, TODO: implement support for sitemap
                       parser = 'xml'           # select xml parser for this file
                       newfilepath = os.path.join(root, os.path.splitext(filename)[0] + ".rss")
                       os.rename(filepath, newfilepath)
                       filepath = newfilepath
                   with open(filepath) as f:
                       filetext = f.read() # beautifulsoup: convert anything to utf-8 via unicode,dammit
                   print "Fixing links in ", filepath
                   # define output encoding, in case you want something else 
                   # (not that this matters, since we escape non-ascii chars in html as html entities)
                   encoding = "utf-8"
                   newtext = fixUrls(filetext, parser, encoding)
                   with open(filepath, 'w') as f:
                       f.write(newtext)

    elif arguments['preview']:
        os.chdir(static_path)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", 9000), Handler)

        print "Serving at port 9000"
        # gracefully handle interrupt here
        httpd.serve_forever()

    elif arguments['setup']:
        if arguments['--gh-repo']:
            repo_url = arguments['--gh-repo']
        else:
            repo_url = raw_input("Enter the Github repository URL:\n").strip()

        # Create a fresh new static files directory
        if os.path.isdir(static_path):
            confirm = raw_input("This will destroy everything inside static/."
                                " Are you sure you want to continue? (y/N)").strip()
            if confirm != 'y' and confirm != 'Y':
                sys.exit(0)
            shutil.rmtree(static_path)

        # User/Organization page -> master branch
        # Project page -> gh-pages branch
        branch = 'gh-pages'
        regex = re.compile(".*[\w-]+\.github\.(?:io|com).*")
        if regex.match(repo_url):
            branch = 'master'

        # Prepare git repository
        repo = Repo.init(static_path)
        git = repo.git

        if branch == 'gh-pages':
            git.checkout(b='gh-pages')
        repo.create_remote('origin', repo_url)

        # Add README
        file_path = os.path.join(static_path, 'README.md')
        with open(file_path, 'w') as f:
            f.write('# Blog\nPowered by [Ghost](http://ghost.org) and [Buster](https://github.com/axitkhurana/buster/).\n')

        print "All set! You can generate and deploy now."

    elif arguments['deploy']:
        repo = Repo(static_path)
        repo.git.add('.')

        current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        repo.index.commit('Blog update at {}'.format(current_time))

        origin = repo.remotes.origin
        repo.git.execute(['git', 'push', '-u', origin.name,
                         repo.active_branch.name])
        print "Good job! Deployed to Github Pages."

    elif arguments['add-domain']:
        repo = Repo(static_path)
        custom_domain = arguments['<domain-name>']

        file_path = os.path.join(static_path, 'CNAME')
        with open(file_path, 'w') as f:
            f.write(custom_domain + '\n')

        print "Added CNAME file to repo. Use `deploy` to deploy"

    else:
        print __doc__

if __name__ == '__main__':
    main()