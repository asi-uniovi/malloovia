#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages
from glob import glob

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [
    'pyyaml',
    'jsonschema',
    'pulp'
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

setup(
    name='malloovia',
    version='0.1.0',
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
)
