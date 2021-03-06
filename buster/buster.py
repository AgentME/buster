"""Ghost Buster. Static site generator for Ghost.
"""

import os
import subprocess
from pathlib import PurePath, PurePosixPath
import re
import json
import sys
import fnmatch
from glob import iglob
import shutil
from itertools import chain
from http.server import HTTPServer, SimpleHTTPRequestHandler
from time import gmtime, strftime
from io import StringIO, BytesIO
from bs4 import BeautifulSoup
from lxml import etree, html
import subresource_integrity
import argparse
import _version
from normpath import normpath

def main():

# Declare argparse options
    parser = argparse.ArgumentParser(description='Ghost Buster. Static site generator for Ghost.',
        prog='buster',
        add_help=True,
        epilog='Powered by ectoplasm.',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser._optionals.title = "options"

    parser.add_argument('--version', action='version', version=_version.__version__)

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
    generate_parser.add_argument('--header', dest='headers', action='append', nargs=1, help='Extra header to include in requests')
    generate_parser.add_argument('--user', dest='user', action='store', nargs=1, help='HTTP user')
    generate_parser.add_argument('--password', dest='password', action='store', nargs=1, help='HTTP password')
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

    print("Running: buster " + args.current_action)

    extra_wget_options = []
    for header in args.headers or []:
        extra_wget_options.append('--header')
        extra_wget_options.append(header[0])
    if args.user is not None:
        extra_wget_options.append('--user')
        extra_wget_options.append(args.user[0])
    if args.password is not None:
        extra_wget_options.append('--password')
        extra_wget_options.append(args.password[0])

    # simplify comparison
    action = args.current_action


    if action == 'generate':
        def download_paths(relpaths):
            if len(relpaths) == 0:
                return
            command = (
                "wget",
                "--level=0",               # keep following links
                "--recursive",             # follow links to download entire site
                "--convert-links",         # make links relative
                "--page-requisites",       # grab everything: css / inlined images
                "--no-parent",             # don't go to parent level
                "--directory-prefix", args.static_path, # download contents to static/ folder
                "--no-host-directories",   # don't create domain named folder
                "--restrict-file-name=unix", # don't escape query string
                *extra_wget_options,
                *(args.source + x for x in relpaths)
            )
            subprocess.run(command, check=True)

        def download_one_file_to_destination(url, destination):
            command = (
                "wget",
                "-O", destination,
                "--restrict-file-name=unix",
                *extra_wget_options,
                url
            )
            subprocess.run(command, check=True)

        download_paths((
            '',
            '/robots.txt',
            '/sitemap.xml',
            '/sitemap-pages.xml',
            '/sitemap-posts.xml',
            '/sitemap-authors.xml',
            '/sitemap-tags.xml'
        ))

        more_rss_paths = []
        for dir in ['tag', 'author']:
            sdir = os.path.join(args.static_path, dir)
            if os.path.isdir(sdir):
                for subdir in os.listdir(sdir):
                    more_rss_paths.append('/' + dir + '/' + subdir + '/rss/')
        download_paths(more_rss_paths)

        for filename in iglob(os.path.join(args.static_path, 'public', 'ghost-sdk*.js*')):
            os.remove(filename)

        # init list of renamed files
        files = []
        # remove query string since Ghost 0.4
        for root, dirs, filenames in os.walk(args.static_path):
            for filename in fnmatch.filter(filenames, '*[?]*'):
                newname = re.sub(r'\?.*', '', filename)
                print("Rename " + filename + " => " + newname)
                os.rename(os.path.join(root, filename), os.path.join(root, newname))
                files.append(newname) # add new name to file-list

        # remove superfluous "index.html" from relative hyperlinks found in text
        abs_url_regex = re.compile(r'^(?:[a-z]+:)?//', flags=re.IGNORECASE)

        # form regex from file-list (i.e. all files, with stripped arguments from above)
        url_suffix_regex = re.compile(r'(' + "|".join(files) + r')(\?.*?(?=\"))', flags = re.IGNORECASE)

        source_url_regex = re.compile('^' + re.escape(args.source))

        # The URLs of all external files we've internalized
        downloaded_external_scripts = set()

        def calculate_sri(filename, hash):
            with open(filename, 'rb') as f:
                data = f.read()
            return str(list(subresource_integrity.generate(data, [hash]))[0])

        def repl(m): # select regex matching group
            print("---Removing " + m.group(2) + " from " + m.group(1))
            return m.group(1)

        def fixAllUrls(relpath, data, kind):
            # step 1:
            # load HTML/XML in lxml
            if kind == "xml": # parser for XML that keeps CDATA elements (beautifulsoup doesn't)
                print("Fixing XML")
                parser = etree.XMLParser(encoding='utf-8', strip_cdata=False, resolve_entities=True)
                data = etree.XML(data.encode(), parser)
                # format the parsed xml for output (keep all non-ascii chars inside CDATA)
                data = etree.tostring(data, pretty_print=True, encoding="utf-8", xml_declaration=True).decode()
            elif kind == "html": # parser for HTML ("lenient" setting for html5)
                print("Fixing HTML")

                # the following should work, but spits out utf-8 numeric character references...
                # TODO: FIXME
                # parser = etree.HTMLParser(strip_cdata=False)
                # if isinstance(data, str):
                #     data = unicode(data, "utf-8")
                # data = etree.parse(StringIO(data), parser)
                # data = html.tostring(data.getroot(), pretty_print=True, method="html")
                # data = u'<!DOCTYPE html>\n' + unicode(data)

                # go through fixTagsOnly (we'll be calling bs4 twice until above is fixed...)
                data = fixTagsOnly(relpath, data, kind)

                # BeautifulSoup outputs html entities with formatter="html" (if you need them).
                # lxml above should be faster, but outputs utf-8 numeric char refs
                print("Fixing remaining links")
                data = BeautifulSoup(data, "html5lib").prettify(formatter="minimal")

            # step 2:
            # substitute all occurences of --source-url (args.source) argument with --target-url (args.target)
            data = re.sub(re.escape(args.source), lambda _: args.target, data)

            # step 3:
            # remove URL arguments (e.g. query string) from renamed files
            # TODO: make it work with googlefonts
            data = url_suffix_regex.sub(repl, data)
            return data

        def fixTagsOnly(relpath, data, kind):
            print("Fixing tags")
            if kind == 'xml':
                parser = etree.XMLParser(encoding='utf-8', strip_cdata=False, resolve_entities=True)
                root = etree.fromstring(data.encode(), parser)

                for el in root.xpath('//*[self::link or self::url or local-name()="loc"]'):
                    el.text = re.sub(source_url_regex, lambda _: args.target, el.text)
                    # /favicon.png is a redirect in ghost, so no favicon.png exists.
                    if el.text == args.target + '/favicon.png':
                        el.text = args.target + '/favicon.ico'
                for el in root.xpath('//*[@href]'):
                    el.attrib['href'] = re.sub(source_url_regex, lambda _: args.target, el.attrib['href'])
                for el in root.xpath('//*[local-name()="link" and namespace-uri()="http://www.w3.org/2005/Atom" and @href and @rel="self" and @type="application/rss+xml"]'):
                    el.attrib['href'] = re.sub(r'/rss/$', '/rss/index.xml', el.attrib['href'])

                return etree.tostring(root, encoding='utf-8', pretty_print=True, xml_declaration=True).decode()
            elif kind == 'html':
                parser = etree.HTMLParser(encoding='utf-8')
                root = etree.fromstring(data.encode(), parser)

                # Remove ghost API javascript. Static files don't need this.
                for el in root.xpath('//script[@type="text/javascript"][contains(@src,"public/ghost-sdk.")][contains(@src,".js")]'):
                    el.getparent().remove(el)
                for el in root.xpath('//script[@type="text/javascript"][not(@src)]'):
                    if re.match(r'\s*ghost\.init\(', el.text):
                        el.getparent().remove(el)

                # Copy any remote static (has integrity attr) javascript files to be local
                for el in root.xpath('//script[@integrity][starts-with(@src,"https:")]'):
                    src = el.attrib['src']
                    integrity = el.attrib['integrity']
                    integrity_hash = integrity.split('-', maxsplit=1)[0]
                    basename_split = os.path.splitext(os.path.basename(src))
                    destination = os.path.join(args.static_path, 'immutable', basename_split[0] + '-' + integrity + basename_split[1])
                    if (
                            destination not in downloaded_external_scripts and
                            (not os.path.isfile(destination) or integrity != calculate_sri(destination, integrity_hash))
                        ):
                        destination_dirname = os.path.dirname(destination)
                        if not os.path.isdir(destination_dirname):
                            os.mkdir(destination_dirname)
                        download_one_file_to_destination(src, destination)
                        dl_integrity = calculate_sri(destination, integrity_hash)
                        if integrity != dl_integrity:
                            os.unlink(destination)
                            print('Expected integrity', repr(integrity))
                            print('Found integrity', repr(dl_integrity))
                            raise Exception('Downloaded file had wrong integrity (' + destination + ')')
                    downloaded_external_scripts.add(destination)
                    el.attrib['src'] = os.path.relpath(destination, os.path.join(args.static_path, os.path.dirname(relpath)))
                    del el.attrib['integrity']
                    if 'crossorigin' in el.attrib:
                        del el.attrib['crossorigin']

                for el in root.xpath('/html/head//link[@rel="canonical" or @rel="amphtml"][@href]'):
                    if not abs_url_regex.search(el.attrib['href']):
                        el.attrib['href'] = args.target + re.sub(r'(/|^)index\.html$', r'\1', normpath(PurePosixPath('/').joinpath(relpath.parent, el.attrib['href'])).as_posix())
                for el in root.xpath('/html/head//meta[@name or @property][@content]'):
                    if re.search(':url$', el.attrib['name'] if 'name' in el.attrib else el.attrib['property']):
                        el.attrib['content'] = re.sub(source_url_regex, lambda _: args.target, el.attrib['content'])
                for el in root.xpath('/html/head/script[@type="application/ld+json"]'):
                    def urlFixer(o):
                        for key, value in o.items():
                            if isinstance(value, str):
                                o[key] = re.sub(source_url_regex, lambda _: args.target, o[key])
                            elif isinstance(value, dict):
                                urlFixer(value)

                    ld = json.loads(el.text)
                    urlFixer(ld)
                    el.text = "\n" + json.dumps(ld, sort_keys=True, indent=4) + "\n"
                for el in root.xpath('//*[@href]'):
                    if not abs_url_regex.search(el.attrib['href']):
                        new_href = re.sub(r'(/|^)rss/index\.html$', r'\1rss/index.xml', el.attrib['href'])
                        new_href = re.sub(r'(/|^)index\.html$', r'\1', new_href)
                        if el.attrib['href'] != new_href:
                            el.attrib['href'] = new_href
                    else:
                        # Fix social sharing links
                        el.attrib['href'] = re.sub(re.escape(args.source), lambda _: args.target, el.attrib['href'])
                        # Fix feedly rss link
                        el.attrib['href'] = re.sub(re.escape(args.target) + '((?:/[^?&]+)?)/rss/([?&]|$)', lambda m: args.target + m.group(1) + '/rss/index.xml' + m.group(2), el.attrib['href'])
                return etree.tostring(root, encoding='utf-8', pretty_print=True, method="html", doctype='<!DOCTYPE html>').decode()
            else:
                raise Exception("Unknown kind " + kind)

        def fixUrls(relpath, data, kind):
            if not args.replace:
                return fixTagsOnly(relpath, data, kind)
            return fixAllUrls(relpath, data, kind)

        # fix links in all html files
        for root, dirs, filenames in os.walk(args.static_path):
            for filename in fnmatch.filter(filenames, 'robots.txt'):
                filepath = os.path.join(root, filename)
                with open(filepath) as f:
                    filetext = f.read()
                newtext = re.sub(re.escape(args.source), lambda _: args.target, filetext)
                with open(filepath, 'w') as f:
                    f.write(newtext)
            for filename in chain(*(fnmatch.filter(filenames, p) for p in ('*.html', '*.xml'))):
                filepath = os.path.join(root, filename)
                relpath = PurePath(os.path.relpath(filepath, args.static_path))
                kind = os.path.splitext(filename)[1][1:] # 'html' or 'xml'
                if root.endswith("/rss"):
                    if kind != 'html':
                        continue
                    # rename index.html in .../rss to index.xml
                    kind = 'xml'
                    newfilepath = os.path.join(root, os.path.splitext(filename)[0] + ".xml")
                    os.rename(filepath, newfilepath)
                    filepath = newfilepath
                with open(filepath) as f:
                    filetext = f.read()
                print("Fixing links in " + filepath)
                newtext = fixUrls(relpath, filetext, kind)
                with open(filepath, 'w') as f:
                    f.write(newtext)

    elif action == 'preview':
        os.chdir(args.static_path)
        server_address = ('', 9000)
        httpd = HTTPServer(server_address, SimpleHTTPRequestHandler)

        print("Serving at port 9000")
        # gracefully handle interrupt here
        httpd.serve_forever()

    elif action == 'setup':
        raise NotImplementedError("TODO update to use python3-compatible library")
        # repo_url = args.repository

        # # Create a fresh new static files directory
        # if os.path.isdir(args.static_path):
        #     confirm = input("This will destroy everything inside " + args.static_path +
        #                         " Are you sure you wish to continue? (y/N)").strip()
        #     if confirm != 'y' and confirm != 'Y':
        #         sys.exit(0)
        #     shutil.rmtree(args.static_path)

        # # User/Organization page -> master branch
        # # Project page -> gh-pages branch
        # branch = 'gh-pages'
        # regex = re.compile(r".*[\w-]+\.github\.(?:io|com).*")
        # if regex.match(repo_url):
        #     branch = 'master'

        # # Prepare git repository
        # repo = Repo.init(args.static_path)
        # git = repo.git

        # if branch == 'gh-pages':
        #     git.checkout(b='gh-pages')
        # repo.create_remote('origin', repo_url)

        # # Add README
        # file_path = os.path.join(args.static_path, 'README.md')
        # with open(file_path, 'w') as f:
        #     f.write('# Blog\nPowered by [Ghost](http://ghost.org) and [Buster](https://github.com/axitkhurana/buster/).\n')

        # print("All set! You can generate and deploy now.")

    elif action == 'deploy':
        raise NotImplementedError("TODO update to use python3-compatible library")
        # repo = Repo(args.static_path)
        # repo.git.add('.')

        # current_time = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        # repo.index.commit('Blog update at {}'.format(current_time))

        # origin = repo.remotes.origin
        # repo.git.execute(['git', 'push', '-u', origin.name,
        #                  repo.active_branch.name])
        # print("Good job! Deployed to Github Pages.")

    elif action == 'add-domain':
        raise NotImplementedError("TODO update to use python3-compatible library")
        # repo = Repo(args.static_path)
        # custom_domain = args.target

        # file_path = os.path.join(args.static_path, 'CNAME')
        # with open(file_path, 'w') as f:
        #     f.write(custom_domain + '\n')

        # print("Added CNAME file to repo. Use `deploy` to deploy")

    else: # probably unnecessary
        parser.print_help()

if __name__ == '__main__':
    main()
