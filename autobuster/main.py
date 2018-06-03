#!/usr/bin/env python3

import glob
import hashlib
import inotify.adapters
import os
import shutil
import subprocess
import tempfile
import time

# This script waits for modifications to the ghost.db file, creates a
# data_... directory, runs buster in it, and then updates the "current"
# symlink to point to the data_... directory.

db_filename = '/var/lib/ghost/content/data/ghost.db'

os.chdir('/var/static_ghost')

GC_TIME_SECONDS = int(os.environ["GC_TIME_SECONDS"])

def file_hash(filename):
    h = hashlib.sha256()
    with open(filename, 'rb', buffering=0) as f:
        for b in iter(lambda: f.read(128*1024), b''):
            h.update(b)
    return h.hexdigest()


try:
    with open('current_db_hash.txt', 'r') as f:
        current_db_hash = f.read().rstrip()
except FileNotFoundError:
    current_db_hash = None


def handle_change():
    global current_db_hash
    if current_db_hash == file_hash(db_filename):
        print('db hash unchanged, ignoring modification')
        return

    print('Modification detected. Waiting before running buster...')
    time.sleep(10)
    new_hash = file_hash(db_filename)

    timestamp = time.strftime('%Y%m%d%H%M', time.gmtime())
    data_dir = tempfile.mkdtemp(prefix='data_' + timestamp + '.', dir='.')

    try:
        os.chmod(data_dir, 0o755)  # owner-read-write, world-readable
        args = [
            "python3", "/var/buster/buster/buster.py",
            "generate", os.environ["GHOST_ADDRESS"], os.environ["STATIC_ADDRESS"],
            "--path", data_dir
        ]
        if "BUSTER_PASSWORD" in os.environ:
            args.extend(("--user", "buster", "--password", os.environ["BUSTER_PASSWORD"]))
        subprocess.run(args, check=True)
        os.symlink(data_dir, data_dir + '-symlink')
    except:
        shutil.rmtree(data_dir)
        raise

    os.replace(data_dir + '-symlink', 'current')
    print('Updated current')

    current_db_hash = new_hash
    with open('current_db_hash.txt', 'w') as f:
        f.write(current_db_hash)
        f.write('\n')

    # Delete the old data_ folders.
    for old_data_dir in glob.iglob('data_*'):
        if os.path.samefile(old_data_dir, data_dir):
            continue
        if time.time() - os.path.getmtime(old_data_dir) < GC_TIME_SECONDS:
            continue
        shutil.rmtree(old_data_dir)
        print('Removed old data directory: ' + old_data_dir)


i = inotify.adapters.Inotify()
i.add_watch(db_filename)

try:
    # There might have been a change to the database while this script wasn't
    # running, so check it now. Note that we're doing the check after we set
    # up the inotify listener, so we don't miss any changes that happen during
    # this function call.
    handle_change()

    for event in i.event_gen():
        if event is None:
            continue
        (header, type_names, watch_path, filename) = event
        if 'IN_MODIFY' not in type_names:
            continue
        handle_change()
finally:
    i.remove_watch(db_filename)
