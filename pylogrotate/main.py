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
    'prerotate': [],
    'postrotate': [],
}
CONFIG_TEMPLATE = '''---
- paths:
  - "*.log"
  - "x/*.log"
rotate: 7
mode: 0640
user: root
group: root
dateformat: "-%Y%m%d%H%M%S"
sharedscripts: yes
prerotate:
  - echo prerotate1
  - echo prerotate2
postroute:
  - echo postrotate
  - echo postrotate2
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
        self.prerotates = config['prerotate']
        self.postrotates = config['postrotate']

    def get_rotated_time(self, path):
        dateext = path.rsplit('-', 1)[-1]
        return datetime.datetime.strptime('-{}'.format(dateext), self.dateformat)

    def is_rotated_file(self, path):
        try:
            return bool(self.get_rotated_time(path))
        except:
            return False

    def remove_old_files(self, file_path):
        glob_path = '{}-[0-9]*'.format(file_path)
        files = [f for f in glob.glob(glob_path) if self.is_rotated_file(f)]
        files.sort(key=self.get_rotated_time, reverse=True)
        for f in files[self.keep_files:]:
            os.remove(f)

    def rotate(self):
        if self.sharedscripts:
            self.prerotate()

        for f in iterate_log_paths(self.config['paths']):
            if not self.sharedscripts:
                self.prerotate()
            dest_path = '{}{}'.format(f, self.dateext)
            shutil.move(f, dest_path)
            os.chmod(dest_path, self.mode)
            chown(dest_path, self.user, self.group)
            self.remove_old_files(f)

            if not self.sharedscripts:
                self.postrotate()

        if self.sharedscripts:
            self.postrotate()

    def prerotate(self):
        for cmd in self.prerotates:
            retcode = subprocess.call(cmd, shell=True)
            if retcode != 0:
                sys.exit(retcode)

    def postrotate(self):
        for cmd in self.postrotates:
            retcode = subprocess.call(cmd, shell=True)
            if retcode != 0:
                sys.exit(retcode)


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
