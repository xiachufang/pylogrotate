import glob
import os
import sys
import datetime
import yaml
import shutil
import subprocess
import pwd
import grp
import argparse


DEFAULT_CONFIG = {
    'paths': [],
    'rotate': 7,
    'mode': 0644,
    'user': 'root',
    'group': 'root',
    'dateformat': '-%Y%m%d',
    'sharedscripts': True,
    'destext': 'rotates/%Y%m/%d',
    'prerotate': [],
    'postrotate': [],
}
CONFIG_TEMPLATE = '''---
- paths:
    - "*.log"
  rotate: 7
  mode: 0640
  user: nobody
  group: nobody
  dateformat: "-%Y%m%d%H%M%S"
  sharedscripts: yes
  destext: "rotates/%Y%m/%d"
  prerotate:
    - echo prerotate2
  postrotate:
    - invoke-rc.d nginx rotate >/dev/null 2>&1 || true
'''


def chown(path, user, group):
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid)


def parse_config(path):
    if isinstance(path, basestring):
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


def generate_default_config():
    with open('default.yml', 'w') as f:
        f.write(CONFIG_TEMPLATE)


def iterate_log_paths(globs):
    for g in globs:
        for f in glob.iglob(g):
            yield f


def run(cmd):
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    pipe.wait()
    if pipe.returncode != 0:
        print pipe.stdout.read()
        print >> sys.stderr, pipe.stderr.read()
        sys.exit(pipe.returncode)


class Rotator(object):
    def __init__(self, config):
        self.config = config
        self.dateformat = config['dateformat']
        self.keep_files = int(config['rotate'])
        self.now = datetime.datetime.now()
        self.dateext = self.now.strftime(self.dateformat)
        self.mode = config['mode']
        self.user = config['user']
        self.group = config['group']
        self.sharedscripts = config['sharedscripts']
        self.destext = config['destext']
        self.prerotates = config['prerotate']
        self.postrotates = config['postrotate']

    def get_rotated_dir(self, path):
        destext = self.now.strftime(self.destext)
        dest_dir = '{}-{}'.format(path, destext)
        return dest_dir

    def get_rotated_time(self, path):
        dateext = path.rsplit('-', 1)[-1]
        return datetime.datetime.strptime('-{}'.format(dateext), self.dateformat)

    def is_rotated_file(self, path):
        try:
            return bool(self.get_rotated_time(path))
        except:
            return False

    def get_dest_path(self, path):
        rotated_dir = self.get_rotated_dir(path)
        filename = os.path.split(path)[-1]
        dest_path = os.path.join(rotated_dir, '{}{}'.format(filename, self.dateext))
        return dest_path

    def remove_old_files(self, path):
        glob_path = '{}-[0-9]*'.format(path)
        files = [f for f in glob.glob(glob_path) if self.is_rotated_file(f)]
        files.sort(key=self.get_rotated_time, reverse=True)
        for f in files[self.keep_files:]:
            os.remove(f)

    def create_rotated_dir(self, path):
        rotated_dir = self.get_rotated_dir(path)
        try:
            os.makedirs(rotated_dir, 0755)
        except OSError as e:
            if e.errno != 17:
                raise
        chown(rotated_dir, self.user, self.group)

    def rotate_file(self, path):
        self.create_rotated_dir(path)
        dest_path = self.get_dest_path(path)
        shutil.move(path, dest_path)
        os.chmod(dest_path, self.mode)
        chown(dest_path, self.user, self.group)
        self.remove_old_files(dest_path)

    def rotate(self):
        if self.sharedscripts:
            self.prerotate()

        for f in iterate_log_paths(self.config['paths']):
            if not self.sharedscripts:
                self.prerotate()

            self.rotate_file(f)

            if not self.sharedscripts:
                self.postrotate()

        if self.sharedscripts:
            self.postrotate()

    def prerotate(self):
        for cmd in self.prerotates:
            run(cmd)

    def postrotate(self):
        for cmd in self.postrotates:
            run(cmd)


def main():
    parser = argparse.ArgumentParser(description='Rotate logs.')
    parser.add_argument('-c', '--config', help='Path to config.', type=argparse.FileType('r'))
    parser.add_argument('-g', '--generate', action='store_true', help='Generate a default config.')
    args = parser.parse_args()
    if not args.config and not args.generate:
        parser.print_help()
        sys.exit(0)

    if args.generate:
        generate_default_config()
        sys.exit(0)

    configs = parse_config(args.config)
    for config in configs:
        r = Rotator(config)
        r.rotate()


if __name__ == '__main__':
    main()
