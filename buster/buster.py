"""Ghost Buster. Static site generator for Ghost.
"""

import os
import re
import sys
import fnmatch
import shutil
import SocketServer
import SimpleHTTPServer
from time import gmtime, strftime
from git import Repo
from io import StringIO, BytesIO
from bs4 import BeautifulSoup
from lxml import etree, html
import argparse

def main():

# Declare argparse options
    parser = argparse.ArgumentParser(description='Ghost Buster. Static site generator for Ghost.',
        version='0.2.0',
        prog='buster',
        add_help=True,
        epilog='Powered by ectoplasm.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser._optionals.title = "options"

# Init subparsers
    subparsers = parser.add_subparsers(dest='current_action', title='actions', description='''Choose an action\n(type "%(prog)s action -h" for additional instructions)''')

# Setup command
    setup_parser = subparsers.add_parser('setup', help='Setup Github repository')
    setup_parser._positionals.title = "required"
    setup_parser._optionals.title = "options"
    setup_parser.add_argument('repository', action='store', metavar='repository', help='URL of your gh-pages repository.')
    setup_parser.add_argument('-p', '--path', action='store', dest='static_path', default='static', metavar='output/dir', help='Output path of local directory to store static pages. (default: static)')


# Generate command
    generate_parser = subparsers.add_parser('generate', help='Bust the Ghost')
    generate_parser._positionals.title = "required"
    generate_parser.add_argument('source', action='store', default='http://localhost:2368', metavar='source-url', nargs='?', help='Address of local Ghost installation (default: http://localhost:2368)')
    generate_parser.add_argument('-p', '--path', action='store', dest='static_path', default='static', metavar='output/dir', help='Output path of local directory to store static pages. (default: static)')
    generate_parser.add_argument('target', action='store', metavar='target-url', default='http://localhost:2368', nargs='?', help='Address of target root URL (e.g. https://domain.com/path/to/root)')
    # replacement switch
    generate_parser.add_argument('--replace-all', '-a', dest='replace', action='store_true', help='Replace all occurences of source-url, not just in link attributes')

# Preview command
    preview_parser = subparsers.add_parser('preview', help='Local preview', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    preview_parser._optionals.title = "options"
    preview_parser.add_argument('-p', '--path', action='store', dest='static_path', default='static', metavar='output/dir', nargs="?", help='Output path of local directory to store static pages. (default: static)')

# Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy to Github pages', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    deploy_parser._optionals.title = "options"
    deploy_parser.add_argument('-p', '--path', action='store', dest='static_path', default='static', metavar='output/dir', nargs='?', help='Output path of local directory to store static pages. (default: static)')

# Add-Domain command
    add_parser = subparsers.add_parser('add-domain', help='Add CNAME to repository', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    add_parser._positionals.title = "required"
    add_parser._optionals.title = "options"
    add_parser.add_argument('target', action="store", metavar='target-domain', help='Address of target URL')
    add_parser.add_argument('-p', '--path', action='store', dest='static_path', metavar='output/dir', nargs='?', help='Output path of local directory to store static pages. (default: static)')

    # print help, when run without arguments
    if len(sys.argv)==1:
        parser.print_help()
        sys.exit(1)
    args=parser.parse_args()

    print "Running: buster " + args.current_action

    # simplify comparison
    action = args.current_action


    if action == 'generate':
        command = ("wget "
                   "--level=0 "               # keep following links
                   "--recursive "             # follow links to download entire site
                   "--convert-links "         # make links relative
                   "--page-requisites "       # grab everything: css / inlined images
                   "--no-parent "             # don't go to parent level
                   "--directory-prefix {1} "  # download contents to static/ folder
                   "--no-host-directories "   # don't create domain named folder
                   "--restrict-file-name=unix "  # don't escape query string
                   "{0}").format(args.source, args.static_path)
        os.system(command)

        # init list of renamed files
        files = list()

        # remove query string since Ghost 0.4
        file_regex = re.compile(r'.*?(\?.*)')
        for root, dirs, filenames in os.walk(args.static_path):
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
                print "Fixing XML"
                parser = etree.XMLParser(encoding=encoding, strip_cdata=False, resolve_entities=True)
                data = etree.XML(data, parser)
                # format the parsed xml for output (keep all non-ascii chars inside CDATA)
                data = etree.tostring(data, pretty_print=True, encoding=encoding)
            if parser == "lxml": # parser for HTML ("lenient" setting for html5)
                print "Fixing HTML"

                # the following should work, but spits out utf-8 numeric character references...
                # TODO: FIXME
                # parser = etree.HTMLParser(encoding=encoding, strip_cdata=False)
                # if isinstance(data, str):
                #     data = unicode(data, encoding)
                # data = etree.parse(StringIO(data), parser)
                # data = html.tostring(data.getroot(), pretty_print=True, method="html")
                # data = u'<!DOCTYPE html>\n' + unicode(data)

                # go through fixTagsOnly (we'll be calling bs4 twice until above is fixed...)
                data = fixTagsOnly(data, parser, encoding)

                # BeautifulSoup outputs html entities with formatter="html" (if you need them).
                # lxml above should be faster, but outputs utf-8 numeric char refs
                print "Fixing remaining links"
                data = BeautifulSoup(data, "html5lib").prettify(encoding,formatter="minimal")

            # step 2:
            # substitute all occurences of --source-url (args.source) argument with --target-url (args.target)
            data = re.sub(args.source, args.target, data)

            # step 3:
            # remove URL arguments (e.g. query string) from renamed files
            # TODO: make it work with googlefonts
            data = url_suffix_regex.sub(repl, data)
            return data

        def fixTagsOnly(data, parser, encoding):
            print "Fixing tags"
            soup = BeautifulSoup(data, parser) # TODO: replace beautifulsoup with lxml (still beats pyQuery, though)
            # adjust all href attributes of html-link elements
            for a in soup.select('a, link'):                                           # for each <a> element
                if not a.has_attr('href'):
                    continue
                if not abs_url_regex.search(a['href']):                                 # that is not an absolute URL
                    new_href = re.sub(r'rss/index\.html$', 'rss/index.rss', a['href'])  # adjust href 1 (rss feed)
                    new_href = re.sub(r'/index\.html$', '/', new_href)                  # adjust href 2 (dir index),
                    print "\t", a['href'], "=>", new_href                               # brag about it,
                    a['href'] = new_href                                                # perform replacement, and
            return soup.prettify(encoding,formatter="html") # return pretty utf-8 html with encoded html entities

        def fixUrls(data, parser, encoding):
            # Is this is a HTML document AND are we looking only for <a> tags?
            if parser == 'lxml' and not args.replace:
                return fixTagsOnly(data, parser, encoding)

            # Otherwise, fall through to fixAllUrls() for all other cases (i.e. currently: replace all urls)
            # (XML needs to always go through here AND we want to replace all URLs)
            return fixAllUrls(data, parser, encoding)

        # fix links in all html files
        for root, dirs, filenames in os.walk(args.static_path):
            for filename in fnmatch.filter(filenames, "*.html"):
                filepath = os.path.join(root, filename)
                parser = 'lxml'              # beautifulsoup parser selection (i.e. lxml)
                if root.endswith("/rss"):    # rename index.html in .../rss to index.rss, TODO: implement support for sitemap
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

    elif action == 'preview':
        os.chdir(args.static_path)

        Handler = SimpleHTTPServer.SimpleHTTPRequestHandler
        httpd = SocketServer.TCPServer(("", 9000), Handler)

        print "Serving at port 9000"
        # gracefully handle interrupt here
        httpd.serve_forever()

    elif action == 'setup':

        repo_url = args.repository

        # Create a fresh new static files directory
        if os.path.isdir(args.static_path):
            confirm = raw_input("This will destroy everything inside " + args.static_path +
                                " Are you sure you wish to continue? (y/N)").strip()
            if confirm != 'y' and confirm != 'Y':
                sys.exit(0)
            shutil.rmtree(args.static_path)

        # User/Organization page -> master branch
        # Project page -> gh-pages branch
        branch = 'gh-pages'
        regex = re.compile(r".*[\w-]+\.github\.(?:io|com).*")
        if regex.match(repo_url):
            branch = 'master'

        # Prepare git repository
        repo = Repo.init(args.static_path)
        git = repo.git

        if branch == 'gh-pages':
            git.checkout(b='gh-pages')
        repo.create_remote('origin', repo_url)

        # Add README
        file_path = os.path.join(args.static_path, 'README.md')
        with open(file_path, 'w') as f:
            f.write('# Blog\nPowered by [Ghost](http://ghost.org) and [Buster](https://github.com/axitkhurana/buster/).\n')

        print "All set! You can generate and deploy now."

    elif action == 'deploy':
        repo = Repo(args.static_path)
        repo.git.add('.')

        current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        repo.index.commit('Blog update at {}'.format(current_time))

        origin = repo.remotes.origin
        repo.git.execute(['git', 'push', '-u', origin.name,
                         repo.active_branch.name])
        print "Good job! Deployed to Github Pages."

    elif action == 'add-domain':
        repo = Repo(args.static_path)
        custom_domain = args.target

        file_path = os.path.join(args.static_path, 'CNAME')
        with open(file_path, 'w') as f:
            f.write(custom_domain + '\n')

        print "Added CNAME file to repo. Use `deploy` to deploy"

    else: # probably unnecessary
        parser.print_help()

if __name__ == '__main__':
    main()
