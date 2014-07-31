#!/usr/bin/env python

from distutils.core import setup

setup(name='opticsd',
      version='0.9.0',
      description='Python optical data collector',
      author='Edgar Vedvik',
      author_email='edgarmv@uninett.no',
      url='http://github.com/edgar-v/opticsd.git',
      py_modules=['opticsd', 'collect', 'config'],
      scripts=['optics'],
      data_files=[('/etc/opticsd/', ['opticsd.conf', 'README.md']),
                  ('/var/log/opticsd/', ['error.log']),
                  ('/var/run/opticsd/', ['opticsd.pid'])],
)
