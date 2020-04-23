#!/usr/bin/env python
# -*- coding:utf-8 -*-

import io

from setuptools import setup


# NOTE(jkoelker) Subjective guidelines for Major.Minor.Micro ;)
#                Bumping Major means an API contract change.
#                Bumping Minor means API bugfix or new functionality.
#                Bumping Micro means CLI change of any kind unless it is
#                    significant enough to warrant a minor/major bump.
version = '1.2.0'


setup(name='batterytender',
      version=version,
      description='Python API for talking to the Deltran Battery Tender API',
      long_description=io.open('README.rst', encoding='UTF-8').read(),
      keywords='deltran battery tender batterytender',
      author='Jason Kölker',
      author_email='jason@koelker.net',
      license='MIT',
      url='https://github.com/jkoelker/batterytender/',
      packages=['batterytender'],
      install_requires=['requests>=1.0.0',
                        'ttldict',
                        'python-dateutil'],
      )
