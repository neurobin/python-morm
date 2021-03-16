"""Morm manager module.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.2'


import sys
import argparse
from typing import Union, List, Dict, Any
import logging

from morm.db import DB
from morm.migration import Migration

log = logging.getLogger('morm:admin')
log.setLevel(logging.INFO)

def init_project():
    files = {
        '_morm_config_.py': """
from morm.db import Pool

DB_POOL = Pool(
    dsn='postgres://',
    host='localhost',
    port=5432,
    user='user',
    password='pass',
    database='db_name',
    min_size=10,
    max_size=90,
)
            """,
        'mgr.py': """
import os
from morm.migration import migration_manager
from _morm_config_ import DB_POOL

from app.models import SomeModel, SomeOtherModel        # change accordingly

MIGRATION_BASE_PATH = os.path.realpath('_migrations_')

migration_models = [
    SomeModel,                                          # change accordingly
    SomeOtherModel,                                     # change accordingly
]

if __name__ == '__main__':
    migration_manager(DB_POOL, MIGRATION_BASE_PATH, migration_models)
"""

    }

    for name, content in files.items():
        try:
            with open(name, 'x', encoding='utf-8') as f:
                f.write(content)
        except FileExistsError:
            log.exception(f'Skipping creating file: {name}')
    return files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", type=str,
                        help="""Command:
                        init: Initialize a project""")

    args = parser.parse_args()

    if args.cmd == 'init':
        return init_project()
    else:
        raise ValueError(f"E: Invalid command: {args.cmd}")
