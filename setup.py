# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
from codecs import open
from setuptools import setup

sys.path[0:0] = ['snorm']

from version import __version__

def get_readme(filename):
    content = ""
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), 'r', encoding='utf-8') as readme:
            content = readme.read()
    except Exception as e:
        pass
    return content

setup(name="snorm",
      version=__version__,
      author="Md. Jahidul Hamid",
      author_email="jahidulhamid@yahoo.com",
      description="A simple and normal database object relational mapper",
      license="BSD",
      keywords="orm, postgresql",
      url="https://github.com/neurobin/snorm",
      packages=["snorm"],
      long_description=get_readme("README.md"),
      long_description_content_type="text/markdown",
      classifiers=[
        # See: https://pypi.python.org/pypi?:action=list_classifiers
        # 'Development Status :: 5 - Production/Stable',
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
      ],
      install_requires=['asyncpg'],
test_suite="snorm.tests.test")
