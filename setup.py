# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
import sys
from codecs import open
from setuptools import setup, find_packages

sys.path[0:0] = ['morm']

from version import __version__

def get_readme(filename):
    content = ""
    try:
        with open(os.path.join(os.path.dirname(__file__), filename), 'r', encoding='utf-8') as readme:
            content = readme.read()
    except Exception as e:
        pass
    return content

setup(name="morm",
      version=__version__,
      author="Md. Jahidul Hamid",
      author_email="jahidulhamid@yahoo.com",
      description="A minimal asynchronous database object relational mapper",
      license="BSD",
      keywords="async, orm, postgresql",
      url="https://github.com/neurobin/python-morm",
      packages=find_packages(include=('morm*',)),
      long_description=get_readme("README.md"),
      long_description_content_type="text/markdown",
      classifiers=[
        # See: https://pypi.python.org/pypi?:action=list_classifiers
        'Development Status :: 5 - Production/Stable',
        # 'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
      ],
      python_requires='>=3.10.0',
      install_requires=['asyncpg','nest_asyncio', 'pydantic>=2.6.4', 'orjson'],
      scripts=['morm/morm_admin', 'morm/init_fap',],
test_suite="morm.tests.test")
