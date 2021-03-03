"""Migrations utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


from typing import Dict, List, Tuple, Any, Union
import re
import os
import glob
import datetime
import json
from morm.db import DB
from morm.model import ModelBase, ModelType
import morm.exceptions as exc

def Open(path: str, mode: str, **kwargs) -> type(open):
    return open(path, mode, encoding='utf-8', **kwargs)

def _get_changed_fields(curs: Dict[str, str], pres: Dict[str, str]) -> Dict[str, str]:
    ops = {}
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
            ck = next(curs_k)
        except StopIteration:
            ck = None
        try:
            pk = next(pres_k)
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
                    'pre_key': '',
                    'pre_def': '',
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
                        'cur_key': '',
                        'cur_def': '',
                        'key_before': key_before,
                    }

        key_before = pk
    return ops

class Migration():
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
        self.migration_file_pattern = os.path.join(self.migration_dir, f'{self.db_table}_*.json')
        os.makedirs(self.migration_dir, exist_ok=True)

        self.previous_file_path = self._get_previous_migration_file_path()
        self.previous_file_name = os.path.basename(self.previous_file_path)
        self.current_file_name = self._get_current_migration_file_name(self.previous_file_name)
        self.current_file_path = os.path.join(self.migration_dir, self.current_file_name)

        with Open(self.previous_file_path, 'r') as f:
            self.previous_json = json.load(f)
        with Open(self.current_file_path, 'r') as f:
            self.current_json = json.load(f)

        self.default_json = {
            'db_table': self.db_table,
            'fields': [],
        }
        self.fields = self._get_fields()

    def _get_fields(self):
        fields = self.model._get_all_fields_()
        for k, v in fields:
            fields[k] = v.sql_def
        return fields

    def _get_previous_migration_file_path(self) -> str:
        """Get latest migration file.

        Raises:
            IndexError: when no files found

        Returns:
            str: file path
        """
        files = glob.glob(self.migration_file_pattern)
        if files:
            return files[-1]
        return ''

    def _get_current_migration_file_index(self, previous_file_name: str) -> int:
        if not previous_file_name:
            return 1
        m = re.match(f'^{self.db_table}_0*(\\d+)\\D*\.json$', previous_file_name)
        try:
            return int(m.group(1)) + 1
        except AttributeError:
            raise ValueError(f"Invalid migration file name: {previous_file_name}")

    def _get_current_migration_file_name(self, previous_file_name: str) -> str:
        cindex = str(self._get_current_migration_file_index(previous_file_name))
        cindex = '0' * (self.index_length - len(cindex)) + cindex
        return f"{self.db_table}_{cindex}_{str(datetime.datetime.now()).replace(' ', '_')}.json"
