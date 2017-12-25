# coding: utf-8

from __future__ import print_function

import argparse
import datetime
import errno
import glob
import grp
import hdfs
import os
import pwd
import shutil
import socket
import subprocess
import sys
import yaml

from pqueue import Queue

try:
    from Queue import Empty
except ImportError:
    from queue import Empty

if sys.version_info[0] == 2:
    string_types = (str, unicode)
else:
    string_types = (str, bytes)


DEFAULT_CONFIG = {
    'paths': [],
    'mode': '0o644',
    'user': 'root',
    'group': 'root',
    # 'rotate': 7,
    'compress': True,
    'copy': [],
    'copytohdfs': [],
    'hdfs': {},
    'dateformat': '%Y%m%d',
    'destext': 'rotates/%Y%m/%d',
    'fnformat': '{logname}-{timestamp}',
    'sharedscripts': True,
    'prerotate': [],
    'postrotate': [],
    'queuepath': '/tmp/pylogrotate-queue'
}


def chown(path, user, group):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    try:
        os.chown(path, uid, gid)
    except:
        pass


def makedirs(path, mode):
    try:
        os.makedirs(path, mode)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise


def is_empty_file(path):
    return os.path.isfile(path) and os.path.getsize(path) == 0


def parse_config(path):
    if isinstance(path, string_types):
        with open(path) as f:
            config = yaml.load(f)
    else:
        config = yaml.load(path)
    cs = []
    for c in config:
        d = DEFAULT_CONFIG.copy()
        d.update(c)
        cs.append(d)
    return cs


def iterate_log_paths(globs):
    for g in globs:
        for f in glob.iglob(g):
            yield os.path.abspath(f)


def run(cmd):
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    pipe.wait()
    if pipe.returncode != 0:
        print(pipe.stdout.read())
        print(pipe.stderr.read(), file=sys.stderr)
        sys.exit(pipe.returncode)


def gzip(path):
    if not path:
        return
    run('gzip -kf {}'.format(path))


class Rotator(object):

    def __init__(self, config):
        self.paths = config['paths']

        self.mode = int(config['mode'], 8)
        self.user = config['user']
        self.group = config['group']

        # FIXME: Handle rotated files keeping correctly
        # self.keep_files = int(config['rotate'])
        self.compress = config['compress']

        self.copy = config['copy']
        self.copytohdfs = config['copytohdfs']
        self.hdfs_config = config['hdfs']
        self.hdfs_client = None
        if self.hdfs_config:
            self.hdfs_client = hdfs.InsecureClient(**self.hdfs_config)

        self.dateformat = config['dateformat']
        self.now = datetime.datetime.now()
        self.timestamp = self.now.strftime(self.dateformat)
        self.destext = config['destext']

        self.fnformat = config['fnformat']
        if not self.fnformat:
            raise ValueError("'fnformat' cannot be empty")

        self.sharedscripts = config['sharedscripts']
        self.prerotates = config['prerotate']
        self.postrotates = config['postrotate']

        self.queuepath = config['queuepath']
        self.queue_chunksize = 1000
        self.queue_block_timeout = 30
        self.queue = Queue(self.queuepath, self.queue_chunksize)

    def get_rotated_dir(self, path):
        destext = self.now.strftime(self.destext)
        dest_dir = '{}-{}'.format(path, destext)
        return dest_dir

    def get_dest_path(self, path):
        rotated_dir = self.get_rotated_dir(path)
        logname = os.path.basename(path)
        dest_path = os.path.join(rotated_dir, self.fnformat.format(logname=logname, timestamp=self.timestamp, hostname=socket.gethostname()))
        return dest_path

    def create_rotated_dir(self, path):
        rotated_dir = self.get_rotated_dir(path)
        makedirs(rotated_dir, 0o755)
        chown(rotated_dir, self.user, self.group)

    def rename_file(self, path):
        self.create_rotated_dir(path)

        dest_path = self.get_dest_path(path)
        shutil.move(path, dest_path)

        self.queue.put((path, dest_path), timeout=self.queue_block_timeout)

        os.chmod(dest_path, self.mode)
        chown(dest_path, self.user, self.group)
        return dest_path

    def compress_file(self, dest_path):
        gzip(dest_path)
        return '{}.gz'.format(dest_path)

    def _copy_file(self, path, from_, to):
        if not to:
            return
        dest = os.path.normpath(path.replace(from_, to))
        dest_dir = os.path.dirname(dest)
        if not os.path.exists(dest_dir):
            makedirs(dest_dir, 0o755)
            chown(dest_dir, self.user, self.group)
        if path.startswith(from_):
            shutil.copy2(path, dest)

    def copy_file(self, dest_path):
        if isinstance(self.copy, dict):
            self.copy = [self.copy]

        for item in self.copy:
            to = item.get('to')
            from_ = item.get('from', '')
            self._copy_file(dest_path, from_, to)

    def _copy_to_hdfs(self, client, path, from_, to):
        if not to:
            return
        dest = os.path.normpath(path.replace(from_, to))
        if path.startswith(from_):
            client.upload(dest, path, overwrite=True, cleanup=True)

    def copy_to_hdfs(self, path):
        if not (self.copytohdfs and self.hdfs_config):
            return
        for item in self.copytohdfs:
            to = item.get('to')
            from_ = item.get('from', '')
            self._copy_to_hdfs(self.hdfs_client, path, from_, to)

    def secure_copy(self):
        while True:
            try:
                path, rotated_path = self.queue.get_nowait()
                rotated_path_before = rotated_path
                if not os.path.exists(rotated_path):
                    self.queue.task_done()
                    continue

                if self.compress:
                    rotated_path = self.compress_file(rotated_path)

                if self.copy:
                    self.copy_file(rotated_path)

                if self.copytohdfs:
                    self.copy_to_hdfs(rotated_path)

                if self.compress:
                    os.remove(rotated_path_before)

                self.queue.task_done()

            except Empty:
                break
            except Exception as e:
                print(e)
                raise

    def rotate(self):
        if self.sharedscripts:
            self.prerotate()

        for f in iterate_log_paths(self.paths):
            if is_empty_file(f):
                continue

            if not self.sharedscripts:
                self.prerotate()

            self.rename_file(f)

            if not self.sharedscripts:
                self.postrotate()

        if self.sharedscripts:
            self.postrotate()

        self.secure_copy()

    def prerotate(self):
        for cmd in self.prerotates:
            run(cmd)

    def postrotate(self):
        for cmd in self.postrotates:
            run(cmd)


def main():
    parser = argparse.ArgumentParser(description='Rotate logs.')
    parser.add_argument('-c', '--config', help='Path to the config file.', type=argparse.FileType('r'), required=True)

    args = parser.parse_args()

    configs = parse_config(args.config)
    for config in configs:
        r = Rotator(config)
        r.rotate()


if __name__ == '__main__':
    main()
