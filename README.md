[![Build Status](https://travis-ci.org/xiachufang/pylogrotate.svg)](https://travis-ci.org/xiachufang/pylogrotate)

# pylogrotate

Rotate and move logs in minutes.

# Install
```
pip install pylogrotate
```

# Usage
```
usage: pylogrotate [-h] -c CONFIG

Rotate logs.

optional arguments:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the config file.
```

# Sample config
```yaml
---
- paths:
    - "/var/log/nginx/*.log"
  mode: 0o644
  user: nobody
  group: nobody
  compress: yes
  copy:
    - from: /var/log/nginx
      to: /mfs/log/nginx
  copytohdfs:
    - from: /var/log/nginx
      to: /mfs/log/nginx
  hdfs:
    url: http://localhost:50070
    user: xx
  dateformat: "%Y%m%d%H%M%S"
  destext: "rotates/%Y%m/%d"
  sharedscripts: yes
  prerotate:
    - echo prerotate2
  postrotate:
    - invoke-rc.d nginx rotate >/dev/null 2>&1 || true
  queuepath: /tmp/pylogrotate-queue
```
