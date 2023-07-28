"""Morm manager module.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.2'


import sys, os
import argparse
from typing import Union, List, Dict, Any
import logging

from morm.db import DB
from morm.migration import Migration

log = logging.getLogger('morm:admin')
log.setLevel(logging.INFO)

def init_project(py_path, venv):
    APP_NAME = py_path.upper()
    HOME = os.path.expanduser('~')
    files = {
        '_morm_config_.py': """
import os
from morm.db import Pool

APP_NAME = '"""+APP_NAME+"""'

DB_POOL = Pool(
    dsn=os.getenv(f'{APP_NAME}_DB_DSN', 'postgres://'),
    host=os.getenv(f'{APP_NAME}_DB_HOST', 'localhost'),
    port=int(os.getenv(f'{APP_NAME}_DB_PORT', 5432)),
    user=os.environ[f'{APP_NAME}_DB_USER'],
    password=os.environ[f'{APP_NAME}_DB_PASS'],
    database=os.environ[f'{APP_NAME}_DB_DATABASE'],
    min_size=int(os.getenv(f'{APP_NAME}_DB_POOL_MIN_SIZE', 10)),
    max_size=int(os.getenv(f'{APP_NAME}_DB_POOL_MAX_SIZE', 90)),
)

""",
        f'{HOME}/.env_{APP_NAME}': f"""#!/bin/sh
# copy this file to a secure place and update the path in the vact file.
if [ "${APP_NAME}_ENV" = live ]; then
    {APP_NAME}_DB_DSN='postgres://'
    {APP_NAME}_DB_HOST='localhost'
    {APP_NAME}_DB_PORT=5432
    {APP_NAME}_DB_USER='db_user_name'
    {APP_NAME}_DB_PASS='db_user_pass'
    {APP_NAME}_DB_DATABASE='db_name'
    {APP_NAME}_DB_POOL_MIN_SIZE=10
    {APP_NAME}_DB_POOL_MAX_SIZE=90
else
    {APP_NAME}_DB_DSN='postgres://'
    {APP_NAME}_DB_HOST='localhost'
    {APP_NAME}_DB_PORT=5432
    {APP_NAME}_DB_USER='db_user_name'
    {APP_NAME}_DB_PASS='db_user_pass'
    {APP_NAME}_DB_DATABASE='db_name'
    {APP_NAME}_DB_POOL_MIN_SIZE=10
    {APP_NAME}_DB_POOL_MAX_SIZE=90
fi
""",
        'vact': f"""
. {HOME}/.env_{APP_NAME}
. {venv}/bin/activate
""",
        'mgr.py': f"""
import os
from morm.migration import migration_manager
from _morm_config_ import DB_POOL

from {py_path}.core.models.user import User

MIGRATION_BASE_PATH = os.path.realpath('_migrations_')

migration_models = [ # Add models here to enable migration
    User,
]

if __name__ == '__main__':
    migration_manager(DB_POOL, MIGRATION_BASE_PATH, migration_models)
""",
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
    parser.add_argument("-p","--py-path", type=str, default='app',
                        help="""application name or python dotted path""")
    parser.add_argument("-v","--venv", type=str, default='.venv',
                        help="""Venv path""")

    args = parser.parse_args()

    if args.cmd == 'init':
        return init_project(args.py_path, args.venv)
    else:
        raise ValueError(f"E: Invalid command: {args.cmd}")
