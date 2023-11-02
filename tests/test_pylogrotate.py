# coding: utf-8

import grp
import gzip
import io
import os
import pwd
import socket

import pytest
import freezegun

from pylogrotate.main import parse_config, Rotator


CONFIG = '''---
- dateformat: '%Y%m%d%H%M%S'
'''


def get_config(**kwargs):
    config = parse_config(io.StringIO(CONFIG))[0]
    config['user'] = pwd.getpwuid(os.geteuid()).pw_name
    config['group'] = grp.getgrgid(os.getegid()).gr_name
    config.update(kwargs)
    return config


@freezegun.freeze_time('2017-11-13 11:22:33')
@pytest.mark.parametrize(['fnformat', 'result'], [
    ('{logname}', 'access.log-rotates/201711/13/access.log'),
    ('{logname}-{timestamp}', 'access.log-rotates/201711/13/access.log-20171113112233'),
    ('{logname}-{timestamp}.{hostname}', 'access.log-rotates/201711/13/access.log-20171113112233.{}'.format(socket.gethostname())),
])
def test_fnformat(fnformat, result):
    rotator = Rotator(get_config(fnformat=fnformat))
    assert rotator.get_dest_path('access.log') == result


@pytest.mark.parametrize(['phase'], [
    ('prerotate',),
    ('postrotate',),
])
def test_pre_post_rotate(capsys, phase):
    config = get_config()
    # only non-zero return value can produce output, so let the script exit with 1
    config[phase] = ['echo {} && [ 0 -eq 1 ]'.format(phase)]

    rotator = Rotator(config)
    with pytest.raises(SystemExit):
        rotator.rotate()

    out, _ = capsys.readouterr()
    expected_out = bytes('{}\n'.format(phase), 'utf-8')
    assert out == '{}\n'.format(expected_out)


def _traverse(path):
    if path.isfile():
        return path
    return _traverse(path.listdir()[0])


def test_rotate(tmpdir):
    content = b'This log file should be rotated.'

    f = tmpdir.mkdir('nginx').join('access.rotate-this.log')
    f.write(content)

    # `f` exists and is the only file in `nginx/` directory
    assert f.exists()
    assert len(tmpdir.join('nginx').listdir()) == 1

    rotator = Rotator(get_config(paths=[str(f)]))
    rotator.rotate()

    # `f` compressed and moved into `*-rotate/` directory
    assert not f.exists()
    assert len(tmpdir.join('nginx').listdir()) == 1

    rf = _traverse(tmpdir.join('nginx'))
    with gzip.open(str(rf)) as rf:
        assert rf.read() == content


def test_skip_empty_files(tmpdir):
    f = tmpdir.mkdir('nginx').join('access.skip-empty.log')
    f.write('')

    # `f` exists and is the only file in `nginx/` directory
    assert f.exists()
    assert len(tmpdir.join('nginx').listdir()) == 1

    rotator = Rotator(get_config(paths=[str(f)]))
    rotator.rotate()

    # empty file `f` will be skipped and still exist, `*-rotate/` directory won't be created
    assert f.exists()
    assert len(tmpdir.join('nginx').listdir()) == 1
