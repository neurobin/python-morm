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


class MigrationQuery():
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
