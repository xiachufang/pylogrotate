[![Build Status](https://travis-ci.org/xiachufang/pylogrotate.svg)](https://travis-ci.org/xiachufang/pylogrotate)

# pylogrotate
logrotate in minutes

# Install
```
pip install pylogrotate
```

# Usage
```
usage: pylogrotate [-h] [-c CONFIG] [-g]

Rotate logs.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to config.
  -g, --generate        Generate a default config.
```

# Sample config
```yaml
---
- paths:
    - "/var/log/nginx/*.log"
  rotate: 7
  mode: 0640
  user: nobody
  group: nobody
  compress: yes
  copy:
    - from: /var/log/nginx
      to: /mfs/log/nginx
  copytohdfs:
    - from: /var/log/nginx
      to: /mfs/log/nginx
  dateformat: "-%Y%m%d%H%M%S"
  sharedscripts: yes
  destext: "rotates/%Y%m/%d"
  prerotate:
    - echo prerotate2
  postrotate:
    - invoke-rc.d nginx rotate >/dev/null 2>&1 || true
  hdfs:
    url: http://localhost:50070
    user: xx
  'queuepath': '/tmp/pylogrotate-queue'
```
