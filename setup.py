#!/usr/bin/env python

from setuptools import setup, find_packages


install_requires = ['pyyaml', 'hdfs', 'pqueue']


setup(
    name='pylogrotate',
    version='0.0.14',
    description='Logrotate in Python',
    author='gfreezy',
    author_email='gfreezy@gmail.com',
    url='https://github.com/xiachufang/pylogrotate',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    install_requires=install_requires,
    extras_require=dict(test=['pytest', 'freezegun']),
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: Chinese (Simplified)',
        'Programming Language :: Python :: 2.7',
    ],
    entry_points={
        'console_scripts': ['pylogrotate=pylogrotate.main:main'],
    },
    keywords='logrotate',
)
