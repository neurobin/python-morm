"""Migrations utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import asyncio
import asyncpg # type: ignore
from typing import Dict, List, Tuple, Any, Union, Iterator, Callable, Optional
import re
import os, sys, shutil
import glob
import datetime
import json
from pathlib import Path
from morm.db import DB, ModelQuery, Transaction, Pool
from morm.model import ModelBase, ModelType
import morm.exceptions as exc
from morm.fields.field import ColumnConfig
from morm.utils import Open, import_from_path

HOME = str(Path.home())
MIGRATION_CURSOR_DIR = os.path.join(HOME, '.local', 'share', 'morm')
os.makedirs(MIGRATION_CURSOR_DIR, exist_ok=True)


def _get_changed_fields(curs: Dict[str, ColumnConfig],
                        pres: Dict[str, ColumnConfig])\
                        -> Dict[str, Dict[str, Union[None, str, ColumnConfig]]]:
    ops: Dict[str, Dict[str, Union[None, str, ColumnConfig]]] = {}
    cl = len(curs)
    pl = len(pres)
    bl = cl if cl >= pl else pl

    curs_k = iter(curs)
    pres_k = iter(pres)

    c = 0
    key_before = None
    while c < bl:
        c += 1 # loop control
        try:
            ck: Optional[str] = next(curs_k)
        except StopIteration:
            ck = None
        try:
            pk: Optional[str] = next(pres_k)
        except StopIteration:
            pk = None
        if ck:
            if ck in pres:
                # this field existed before
                if curs[ck] != pres[ck]:
                    # This field has been modified.
                    # Things can happen:
                    # 1. The field definition has been modified
                    # Can not handle the following:
                    # 2. The field was deleted and added a new (ignore)
                    # 3. The field was deleted and another one was renamed to this one.
                    # 4. The field was renamed and another one was renamed to this one.
                    ops[ck] = {
                        'op': 'mod',
                        'cur_key': ck,
                        'cur_def': curs[ck],
                        'pre_key': ck,
                        'pre_def': pres[ck],
                        'key_before': key_before,
                    }
            else:
                # This field did not exist before, this is
                # undoubtedly a new field. Either add or rename
                ops[ck] = {
                    'op': 'add',
                    'cur_key': ck,
                    'cur_def': curs[ck],
                    'key_before': key_before,
                }
        if pk:
            if pk in curs:
                # It will be handled by curs handler above.
                pass
            else:
                # pk is either deleted or renamed.
                if ck and ck not in pres:
                    # ck is new and at the position of pk
                    # take as renamed
                    ops[ck] = { # rename overlaps add in above.
                        'op': 'rename',
                        'cur_key': ck,
                        'cur_def': curs[ck],
                        'pre_key': pk,
                        'pre_def': pres[pk],
                        'key_before': key_before,
                    }
                    # if the values are not equal,
                    # then it can happen that pk was deleted and
                    # ck was added at its position, but it can
                    # also happen that pk was renamed and
                    # modified at the same time.
                    # Deleting will be loss of data, thus
                    # throwing error in renaming when the
                    # column definition does not comply
                    # seems much more sensible. One can
                    # do the changes one step at a time
                    # to avoid that error.
                # elif ck and ck in pres:
                #     # ck is not new and at the position of pk.
                #     # where pk no longer exists.
                #     pass
                else:
                    # pk is deleted.
                    ops[pk] = {
                        'op': 'delete',
                        'pre_key': pk,
                        'pre_def': pres[pk],
                        'key_before': key_before,
                    }

        key_before = pk
    return ops

MIGRATION_RUNNER_TEMPLATE = '''
import morm

class MigrationRunner(morm.migration.MigrationRunner):
    """Run migration with pre and after steps.
    """
    migration_query = """{migration_query}"""

    # async def run_before(self):
    #     """Run before migration

    #     self.tdb is the db handle (transaction)
    #     self.model is the model class
    #     """
    #     dbm = self.tdb(self.model)
    #     # # Example
    #     # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
    #     # await dbm.execute()
    #     # # etc..

    # async def run_after(self):
    #     """Run after migration.

    #     self.tdb is the db handle (transaction)
    #     self.model is the model class
    #     """
    #     dbm = self.tdb(self.model)
    #     # # Example
    #     # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
    #     # await dbm.execute()
    #     # # etc..
'''

class MigrationRunner():
    """Run migration with pre and after steps.
    """
    tdb: DB
    model: ModelType
    migration_query: str

    def __init__(self, tdb: DB, model: ModelType):
        self.tdb = tdb
        self.model = model

    async def run_before(self):
        """Run before migration

        self.tdb is the db handle (transaction)
        self.model is the model class
        """
        # dbm = self.tdb(self.model)
        # # Example
        # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
        # await dbm.execute()
        # # etc..
        pass

    async def run_after(self):
        """Run after migration.

        self.tdb is the db handle (transaction)
        self.model is the model class
        """
        # dbm = self.tdb(self.model)
        # # Example
        # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
        # await dbm.execute()
        # # etc..
        pass

    async def _run_migration_query(self):
        try:
            dbm = self.tdb(self.model)
            if self.migration_query:
                await dbm.q(self.migration_query).execute()
        except asyncpg.exceptions.PostgresSyntaxError:
            sys.stderr.write(f'************ Migration Query ************\n{dbm.getq()[0]}\n\n')

    async def run(self):
        """Runs run_before, _run_migration_query and run_after sequentially.
        """
        await self.run_before()
        await self._run_migration_query()
        await self.run_after()






class Migration():
    """Initiate a migration configuration.

    Args:
        model (ModelType): model class
        migration_base_path (str): where to save migration files.
        index_length (int, optional): index length of migration files. Defaults to 8.

    Raises:
        exc.MigrationModelNotAllowedError: For invalid model
    """
    def __init__(self, model: ModelType, migration_base_path: str, index_length=8):
        if model._is_abstract_():
            raise exc.MigrationModelNotAllowedError(f'Abstract model ({model.__name__}) can not be in database')
        if model._is_proxy_():
            raise exc.MigrationModelNotAllowedError(f"Proxy model ({model.__name__}) can not be passed for migration. Do migration with the non-proxy version.")
        self.model = model
        self.migration_base_path = migration_base_path
        self.index_length = index_length
        self.db_table = model._get_db_table_()
        self.migration_dir = os.path.join(migration_base_path, self.db_table)
        self.migration_queue_dir = os.path.join(self.migration_dir, '.queue')
        self.migration_file_pattern = os.path.join(self.migration_dir, f'{self.db_table}_*.json')
        os.makedirs(self.migration_dir, exist_ok=True)
        os.makedirs(self.migration_queue_dir, exist_ok=True)
        self.flatten_migration_dir = os.path.realpath(self.migration_dir).replace(os.path.sep, '_')
        self.migration_cursor_path = os.path.join(MIGRATION_CURSOR_DIR, f'{self.flatten_migration_dir}.cursor')

        self.previous_file_path = self._get_previous_migration_file_path()
        self.previous_file_name = os.path.basename(self.previous_file_path)
        self.current_file_name_without_extention = self._get_current_migration_file_name_without_extension(self.previous_file_name)
        self.current_file_name = f"{self.current_file_name_without_extention}.json"
        self.current_file_path = os.path.join(self.migration_dir, self.current_file_name)
        # self.current_sql_file_name = f'{self.current_file_name}.sql'
        # self.current_sql_file_path = os.path.join(self.migration_queue_dir, self.current_sql_file_name)
        self.current_mgrpy_file_name = f'{self.current_file_name_without_extention}.py'
        self.current_mgrpy_file_path = os.path.join(self.migration_queue_dir, self.current_mgrpy_file_name)
        self.mgrpy_file_pattern = os.path.join(self.migration_queue_dir, '*.py')

        self.default_json = {
            'db_table': self.db_table,
            'fields': {},
        }
        self._fields = self._get_fields()

        pjson = self._get_json_from_file(self.previous_file_path)
        fields = pjson['fields']
        self._pfields: Dict[str, ColumnConfig] = {}
        for k, v in fields.items():
            self._pfields[k] = ColumnConfig(**v)

        self.cjson_fields = {}
        for k, v in self.cfields.items():
            self.cjson_fields[k] = v.to_json()

        self.current_json = self.default_json
        self.current_json['fields'] = self.cjson_fields

    @property
    def cfields(self) -> Dict[str, ColumnConfig]:
        """ColumnConfig for all fields in a dict.

        Returns:
            Dict[str, ColumnConfig]
        """
        return self._fields

    @property
    def pfields(self) -> Dict[str, ColumnConfig]:
        """ColumnConfig for all previous fields in a dict.

        Returns:
            Dict[str, ColumnConfig]
        """
        return self._pfields

    def _get_fields(self) -> Dict[str, ColumnConfig]:
        fields = self.model._get_all_fields_()
        fieldscc: Dict[str, ColumnConfig] = {}
        for k, v in fields.items():
            fieldscc[k] = v.sql_conf
        return fieldscc

    @staticmethod
    def _get_create_table_query(db_table: str, fields: Dict[str, ColumnConfig]) -> str:
        """Get the complete create table query

        Args:
            fields (Dict[str, ColumnConfig]): fields that will be used to create the create quey

        Returns:
            str: query string
        """
        cq0 = f'CREATE TABLE "{db_table}" (\n'
        cq = []
        aq = []
        for k, v in fields.items():
            q, alq = v.get_query_column_create_stub(db_table)
            cq.append(f'    {q}')
            aq.append(alq)
        cqm = ',\n'.join(cq)
        cqe = '\n);'
        create_q = f'{cq0}{cqm}{cqe}'
        alter_q = '\n'.join(aq)
        total_q = f'{create_q}{alter_q}'
        return total_q

    def get_create_table_query(self) -> str:
        """Get a create table query for current fields

        Returns:
            str: query string
        """
        return self._get_create_table_query(self.db_table, self.cfields)

    def _get_json_from_file(self, path: str) -> Dict[str, Any]:
        """Get json from file or return a default json if file does not exist.

        Args:
            path (str): file path

        Returns:
            Dict[str, Any]: json dict
        """
        if not path:
            return self.default_json
        try:
            with Open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.default_json

    def _take_yn(self):
        yn = input("Is this correct? [Y/n]: ")
        if yn != 'Y' and yn != 'y': sys.exit()
        return True

    def _move_to_trash(self, path: str):
        dirn = os.path.dirname(path)
        # n = os.path.basename(path)
        trash = os.path.join(dirn, '.trash')
        os.makedirs(trash, exist_ok=True)
        shutil.move(path, trash)

    def _move_all_to_trash(self, file_list: List[str]):
        for f in file_list:
            self._move_to_trash(f)

    def delete_migration_files(self, start: int, end: int):
        """Delete migration files by index.

        Args:
            start (int): start index
            end (int): end index
        """
        print(f'=> Deleting migration files for model {self.model.__name__}')
        for i in range(start, end+1):
            si = str(i)
            si = '0' * (self.index_length - len(si)) + si
            files = glob.glob(os.path.join(self.migration_dir, f'{self.db_table}_{si}_*.json'))
            self._move_all_to_trash(files)
            pypat = os.path.join(self.migration_queue_dir, f'{self.db_table}_{si}_*.py')
            pyrpat = b'[^\x00]*' + bytes(f'{self.db_table}_{si}_', encoding='utf-8') + b'[^\x00]*\\.py\x00'
            pyfiles = glob.glob(pypat)
            self._move_all_to_trash(pyfiles)
            content = b''
            with open(self.migration_cursor_path, 'rb') as f:
                content = f.read()
                content = re.sub(pyrpat, b'', content)
            tmpf = self.migration_cursor_path + '.tmp'
            with open(tmpf, 'wb') as f:
                f.write(content)
            os.rename(tmpf, self.migration_cursor_path)
        print(f'   Migration files for model {self.model.__name__} have been successfully deleted.')

    def _update_migration_cursor(self, path: str):
        with open(self.migration_cursor_path, 'ab') as f:
            cont = bytes(path, encoding='utf-8') + b'\x00'
            f.write(cont)

    def _get_unapplied_migrations(self) -> List[str]:
        mgrpy_files = sorted(glob.glob(self.mgrpy_file_pattern))
        mgr = iter(mgrpy_files)
        prev_files = []
        try:
            with open(self.migration_cursor_path, 'rb') as f:
                content = f.read().split(sep=b'\x00')
                for cursor in content:
                    if not cursor: continue # split includes a last empty element
                    try:
                        file = next(mgr)
                        if cursor != bytes(file, encoding='utf-8'):
                            raise ValueError(f"Migration file path mismatch, expected {str(cursor)} == {file}")
                        prev_files.append(file)
                    except StopIteration:
                        raise ValueError(f"Migration file/s missing after {str(cursor)}")
        except FileNotFoundError:
            pass
        return mgrpy_files[len(prev_files):]

    async def migrate(self, pool: Pool):
        """Run the migrations created by makemigrations beforehand.

        Args:
            pool (Pool): pool object.
        """
        print(f'=> Applying migrations for model {self.model.__name__}')
        files = self._get_unapplied_migrations()
        if not files:
            print('   Nothing to migrate. Did you run makemigrations ?')
            return None
        for file in files:
            mn = os.path.basename(file).replace('.py','')
            mr = import_from_path(mn, file) # type: ignore
            async with Transaction(pool) as tdb:
                mro: MigrationRunner = mr.MigrationRunner(tdb, self.model)
                await mro.run()
                self._update_migration_cursor(file)
                print(f'   Migration applied: {mn}')

    def make_migrations(self, yes=False, silent=False):
        """Prepare migration files.

        Args:
            yes (bool, optional): confirm yes to all. Defaults to False.
            silent (bool, optional): Suppress message. Defaults to False.
        """
        print(f'=> Making migrations for model {self.model.__name__} ...')
        query = ''
        qs = []
        if self.pfields:
            # changes only
            for q, m in self._migration_query_generator():
                if not q: continue
                if not silent or not yes:
                    print(m)
                if not yes:
                    self._take_yn()
                qs.append(q)
            query = '\n'.join(qs)
        else:
            # new table
            query = self.get_create_table_query()
            print(query)
            if not yes:
                self._take_yn()
        if not query:
            if not silent:
                print(f"   No changes detected for model {self.model.__name__}")
            return None
        with open(self.current_mgrpy_file_path, 'w') as f:
            f.write(MIGRATION_RUNNER_TEMPLATE.format(migration_query=query))
            with open(self.current_file_path, 'w') as jf:
                # print(self.current_json)
                json.dump(self.current_json, jf)
        print(f'*** Migrations for model {self.model.__name__} have been successfully created.')

    def _migration_query_generator(self) -> Iterator[Tuple[str, str]]:
        """Detect changes on model fields and yield query, discriptive message

        Yields:
            Iterator[Tuple[str, str]]: yield query, descriptive_message
        """
        changed = _get_changed_fields(self.cfields, self.pfields)
        for k, v in changed.items():
            op = v['op']
            if op == 'add':
                query, msg = v['cur_def'].get_query_column_add(self.db_table) # type: ignore
            elif op == 'delete':
                query, msg = v['pre_def'].get_query_column_drop(self.db_table) # type: ignore
            elif op == 'mod':
                query, msg = v['cur_def'].get_query_column_modify(v['pre_def'], self.db_table) # type: ignore
            elif op == 'rename':
                rnm_query, rnm_msg = v['cur_def'].get_query_column_rename(v['pre_key'], self.db_table) # type: ignore
                mod_query, mod_msg = v['cur_def'].get_query_column_modify(v['pre_def'], self.db_table) # type: ignore
                query = f'{rnm_query} {mod_query}'
                msg = f"{mod_msg}\n{rnm_msg}"
            else:
                raise ValueError(f"Invalid operation: {op}")
            yield query, f'\n{"*"*79}{msg}\n\n{query}\n{"*"*79}'


    def _get_previous_migration_file_path(self) -> str:
        """Get latest migration file.

        Raises:
            IndexError: when no files found

        Returns:
            str: file path
        """
        files = sorted(glob.glob(self.migration_file_pattern))
        if files:
            return files[-1]
        return ''

    def _get_current_migration_file_index(self, previous_file_name: str) -> int:
        if not previous_file_name:
            return 1
        m = re.match(f'^{self.db_table}_0*(\\d+)_.*\\.json$', previous_file_name)
        try:
            return int(m.group(1)) + 1  # type: ignore
        except AttributeError:
            raise ValueError(f"Invalid migration file name: {previous_file_name}")

    def _get_current_migration_file_name_without_extension(self, previous_file_name: str) -> str:
        cindex = str(self._get_current_migration_file_index(previous_file_name))
        cindex = '0' * (self.index_length - len(cindex)) + cindex
        timestamp = str(datetime.datetime.now())
        timestamp = re.sub(r'[.:\s-]', '_', timestamp)
        return f"{self.db_table}_{cindex}_{timestamp}"


async def _run_with_transaction(pool: Pool, func: Callable, *args: Any, **kwargs: Any):
    await func(pool, *args, **kwargs)

def run_with_transaction(pool: Pool, func: Callable, *args: Any, **kwargs: Any):
    asyncio.get_event_loop().run_until_complete(_run_with_transaction(pool, func, *args, **kwargs))


def migration_manager(pool: Pool, base_path: str, models: List[ModelType]):
    """Migration manager.

    Parses arguments to run migration commands.

    Args:
        pool (Pool): pool object.
        base_path (str): migration base path
        models (List[ModelType]): models to migrate
    """
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", type=str,
                        help="""Command:
                        makemigrations: Create migration files.
                        migrate: Apply migrations created by makemigrations command.
                        delete_migration_files <sart> <end>: Delete migration files from start index to end index.""")
    parser.add_argument('start_index', nargs='?', type=int, default=0, help='Start index for delete_migration_files command')
    parser.add_argument('end_index', nargs='?', type=int, default=0, help='End index for delete_migration_files command')
    parser.add_argument('-y', '--yes', action='store_true', help='Confirm all', default=False)
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress message', default=False)

    args = parser.parse_args()

    if args.cmd == 'makemigrations':
        for model in models:
            Migration(model, base_path).make_migrations(yes=args.yes, silent=args.quiet)
    elif args.cmd == 'migrate':
        for model in models:
            run_with_transaction(pool, Migration(model, base_path).migrate)
    elif args.cmd == 'delete_migration_files':
        if args.start_index == 0:
            raise ValueError(f'start_index and end_index must be given')
        if args.start_index > args.end_index:
            raise ValueError(f'E: Invalid start ({args.start_index}) and end index ({args.end_index})\n')
        for model in models:
            Migration(model, base_path).delete_migration_files(args.start_index, args.end_index)

    else:
        raise ValueError('E: Invalid command: {args.cmd}')
