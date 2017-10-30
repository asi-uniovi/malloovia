#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages
from glob import glob
import os

with open('README.md') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'ruamel.yaml',
    'jsonschema',
    'pulp',
    'click',
    'progress'
]

setup_requirements = [
    'pytest-runner',
]

test_requirements = [
    'pytest',
]

package_data = {
        "samples": [
            'tests/test_data/problems/problem1.yaml',
            'tests/test_data/problems/problem2.yaml',
            'tests/test_data/problems/problem3.yaml',
            ]
        }

data_files = [
        ('example_problems', glob("tests/test_data/problems/*"))
        ]

here = os.path.abspath(os.path.dirname(__file__))
about = {}
with open(os.path.join(here, 'malloovia', '__version__.py'), 'r') as f:
    exec(f.read(), about)

setup(
    name='malloovia',
    version=about['__version__'],
    description="Use linear programming to allocate applications to cloud infrastructure",
    long_description=readme + '\n\n' + history,
    author="ASI Uniovi",
    author_email='jldiaz@uniovi.es',
    url='https://github.com/asi-uniovi/malloovia',
    packages=find_packages(include=['malloovia']),
    include_package_data=True,
    install_requires=requirements,
    license="MIT license",
    zip_safe=False,
    keywords='malloovia',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    test_suite='tests',
    tests_require=test_requirements,
    setup_requires=setup_requirements,
    entry_points='''
        [console_scripts]
        malloovia=malloovia.cli:cli
    '''
)
