"""Morm manager module.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import sys
import argparse
from typing import Union, List, Dict, Any


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", type=str,
                        help="""Command:
                        makemigrations: Create migration files.
                        runmigrations: Apply the migrations created by makemigrations.
                        migrate: Create and apply migrations.
                        delete_migration_files <sart> <end>: Delete migration files from start index to end index.""")
    parser.add_argument('start_index', nargs='?', type=int, default=0, help='Start index for delete_migration_files command')
    parser.add_argument('end_index', nargs='?', type=int, default=0, help='End index for delete_migration_files command')
    parser.add_argument('-y', '--yes', action='store_true', help='Confirm all', default=False)
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress message', default=False)

    args = parser.parse_args()

    if args.cmd == 'makemigrations':
        print('=> Making migrations ...')
    elif args.cmd == 'runmigrations':
        print('=> Applying migrations ...')
    elif args.cmd == 'migrate':
        print('=> Making and applying migrations ...')
    elif args.cmd == 'delete_migration_files':
        if args.start_index == 0:
            raise ValueError(f'start_index and end_index must be given')
        if args.start_index > args.end_index:
            raise ValueError(f'E: Invalid start ({args.start_index}) and end index ({args.end_index})\n')
        print(f'=> Deleting migration files from index {args.start_index} to {args.end_index}')
    else:
        raise ValueError('E: Invalid command: {args.cmd}')
