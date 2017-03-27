# coding: utf-8
import re
import os
import sys
import gzip
import argparse
import datetime
from operator import itemgetter


class Writer(object):

    def __init__(self, log_home, log_tag, rotated_time, subdir_name):
        dirpath_template = os.path.join(log_home, "{subdir_name}/{log_tag}-rotates/%Y/%m/%d/%H")
        dirpath_template = dirpath_template.format(log_tag=log_tag, subdir_name=subdir_name)
        dir_path = rotated_time.strftime(dirpath_template)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path, mode=0751)
        filename_template = "{log_tag}-%Y%m%d%H%M%S.gz".format(log_tag=log_tag)
        filename = rotated_time.strftime(filename_template)
        file_path = os.path.join(dir_path, filename)
        self.file = gzip.open(file_path, mode='wb')

    def __enter__(self):
        return self.file

    def __exit__(self, type, value, traceback):
        print "__exit__:Close %s" % self.file.name
        return self.file.close()


class Reader(object):

    def __init__(self, log_home, log_tag, split_datetime, subdir_name):
        hourly_dirpath_template = os.path.join(log_home, "{subdir_name}/{log_tag}-rotates/%Y/%m/%d/%H")
        hourly_dirpath_template = hourly_dirpath_template.format(log_tag=log_tag, subdir_name=subdir_name)
        dirpath = split_datetime.strftime(hourly_dirpath_template)
        self.split_file_path = self.get_split_file_path(log_tag, split_datetime, dirpath)
        self.iter = self.load_need_to_split_file()

    @classmethod
    def get_split_file_path(cls, log_tag, split_datetime, dirpath):
        if not os.path.exists(dirpath):
            raise OSError("HAVE NOT THIS FOLDER")
        filename_regex = "{log_tag}-(\d{{14}})\.gz".format(log_tag=log_tag)
        filenames = sorted(os.listdir(dirpath))
        datetime_distance_dict = dict()
        for filename in filenames:
            # 解析文件名中间的时间戳，寻找和 split_datetime 最接近的文件
            filename_datetime_str = re.search(filename_regex, filename).groups()[0]
            filename_datetime = datetime.datetime.strptime(filename_datetime_str, '%Y%m%d%H%M%S')
            filepath = os.path.join(dirpath, filename)
            if truncate_hour(datetime.datetime.fromtimestamp(os.path.getctime(filepath))) == truncate_hour(split_datetime):
                datetime_distance_dict[filepath] = abs((filename_datetime - split_datetime).total_seconds())

        return sorted(datetime_distance_dict.items(), key=itemgetter(1))[0][0]

    def load_need_to_split_file(self):
        if not os.path.exists(self.split_file_path):
            raise OSError("HAVE NOT THIS FILE")
        for line in self.read_gz_file(self.split_file_path):
            yield line

    @classmethod
    def read_gz_file(cls, filepath):
        with gzip.open(filepath, 'rb') as f:
            for line in f:
                yield line

    @classmethod
    def extra_datetime(cls, line):
        try:
            splited = line.split('\t')
            time_str = splited[1]
            time_str, time_zone_str = time_str.split(" ")
            dt = datetime.datetime.strptime(time_str, "%d/%b/%Y:%H:%M:%S")
        except:
            raise SyntaxError
        return dt

    def __iter__(self):
        return self

    def next(self):
        next_line = self.iter.next()
        return self.extra_datetime(next_line), next_line

    def __del__(self):
        os.remove(self.split_file_path)


def get_all_tag(log_home='/mfs/log/nginx'):
    tag_name_set = set()
    for subdir_name in os.listdir(log_home):
        tag_dir = os.path.join(log_home, subdir_name)
        tag_name_set |= set(os.listdir(tag_dir))
    for tag_name in tag_name_set:
        if tag_name not in ["track.im_exp.log-rotates", "track.im_clk.log-rotates"]:
            yield tag_name.replace('-rotates', '')


def write(log_home, log_tag, rotated_time, subdir_name, log_matrix):
    with Writer(log_home=log_home, log_tag=log_tag, rotated_time=rotated_time, subdir_name=subdir_name) as f:
        for _log_line in log_matrix:
            f.writelines(_log_line)


def rec_log(split_datetime, log_tag, log_home='/mfs/log/nginx'):
    if not isinstance(split_datetime, datetime.datetime):
        raise TypeError("time_begin and time_end must be type of datetime.datetime")
    for subdir_name in os.listdir(log_home):
        reader = Reader(log_home=log_home, log_tag=log_tag, split_datetime=split_datetime, subdir_name=subdir_name)
        start_time = None
        log_matrix = list()
        for dt, log_line in reader:
            log_matrix.append(log_line)
            if not start_time:
                start_time = dt
            if dt - start_time > datetime.timedelta(minutes=5):
                write(log_home, log_tag, dt, subdir_name, log_matrix)
                start_time = None
                log_matrix = list()
        rotated_time = start_time + datetime.timedelta(minutes=5)
        write(log_home, log_tag, rotated_time, subdir_name, log_matrix)


def truncate_time(d):
    return datetime.datetime.strptime(d, '%Y-%m-%d %H:%M:%S')


def truncate_hour(d):
    return datetime.datetime.strptime(d, '%Y-%m-%d %H')


def main():
    parser = argparse.ArgumentParser(description='Recovery LogRotate')
    parser.add_argument('-d', '--datetime', type=truncate_time, help='the datetime of the need to split the file.')
    parser.add_argument('-t', '--tags', nargs='+', type=list, help='need to split the files log marked.')
    parser.add_argument('-l', '--log_home', type=str, default="/mfs/log/nginx", help='nginx log home dir')
    args = parser.parse_args()
    if not args.datetime:
        parser.print_help()
        sys.exit(0)

    tags = args.tags
    if not tags:
        tags = get_all_tag(args.log_home)

    for tag in tags:
        rec_log(args.datetime, tag, log_home=args.log_home)


if __name__ == '__main__':
    main()
