import pytest
import os
import datetime
from context import cwd
from pylogrotate.main import parse_config, Rotator


def test_parse(config):
    assert config[0]['paths'] == ['/var/log/nginx/*.log']
    assert config[0]['period'] == 'daily'
    assert config[0]['user'] == 'www-data'
    assert config[0]['group'] == 'root'
    assert config[0]['prerotate'] == ['if [ -d /etc/logrotate.d/httpd-prerotate ]; then\n  run-parts /etc/logrotate.d/httpd-prerotate;\nfi']


@pytest.fixture
def config():
    return parse_config(os.path.join(cwd, 'config.yml'))


@pytest.fixture
def rotator(config):
    return Rotator(config[0])


class TestRotater(object):
    def test_get_rotated_time(self, rotator):
        path = '/var/log/nginx/access.log-20160910101030'
        assert rotator.get_rotated_time(path) == datetime.datetime(2016, 9, 10, 10, 10, 30)

    def test_get_rotated_time(self, rotator):
        with pytest.raises(Exception):
            rotator.get_rotated_time('/var/log/nginx/access.log-20160910-1010301')

        with pytest.raises(Exception):
            rotator.get_rotated_time('/var/log/nginx/access.log-201609101')

        with pytest.raises(Exception):
            rotator.get_rotated_time('/var/log/nginx/access.log201609101')

    def test_remove_old_files(self, rotator):
        pass
