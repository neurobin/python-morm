
import unittest
from copy import copy, deepcopy
import pickle
from typing import Dict, List, Tuple, Any
from morm.types import Void, VoidType
import morm.migration as mg
from morm.model import Model, ModelType, Field



def _get_alter_column_sql(self, altdefs: Dict[str, str]) -> Tuple[str, str]:
    """Get alter column sql

    altdefs need to be a dictionary of the following format:

    ```python
    altdefs = {
        'op': str # one of add, delete, rename and mod (modify)
        'cur_key': str # target name of column
        'cur_def': str # definition of target column
        'pre_key': str # current name of column
        'pre_def': str # current definition
        'key_before': str # name of the key (pre_key, current column) before this column, None for first column.
    }
    ```

    Args:
        altdefs (Dict[str, Any]): altdefs dict

    Returns:
        str, str: sql, msg
    """
    self.db_table = '"BigUserTable"'
    op = altdefs['op']
    pre_key = altdefs['pre_key']
    pre_def = altdefs['pre_def']
    cur_key = altdefs['cur_key']
    cur_def = altdefs['cur_def']
    if altdefs['op'] == 'rename':
        msg = f"> RENAME: {pre_key}: {pre_def} --> {cur_key}: {cur_def}"
        if pre_def != cur_def:
            alter_type = f'ALTER TABLE {self.db_table} ALTER COLUMN "{pre_key}" TYPE {cur_def}; '
        else:
            alter_type = ''
        return f'{alter_type}ALTER TABLE {self.db_table} RENAME "{pre_key}" TO "{cur_key}";', msg
    elif op == 'mod':
        msg = f"> MODIFY: {pre_key}: {pre_def} --> {cur_def}"
        return f'ALTER TABLE {self.db_table} ALTER COLUMN "{pre_key}" TYPE {cur_def}', msg
    elif op == 'delete':
        msg = f"> DELETE: {pre_key} {pre_def}"
        return f'ALTER TABLE {self.db_table} DROP COLUMN "{pre_key}"', msg
    elif op == 'add':
        msg = f"> ADD   : {cur_key} {cur_def}"
        return f'ALTER TABLE {self.db_table} ADD "{cur_key}" {cur_def}', msg
    return '', ''



class TestMethods(unittest.TestCase):
    def test_func(self):

        curs = {
            'name': 'varchar(255)',
            'profession': 'varchar(255)',
            'age': 'int',
            'hobby': 'varchar(255)',
            'height': 'int',
            'weight': 'int',
        }
        pres = {
            'profession': 'varchar(25)',
            'age': 'int',
            'address': 'varchar(255)',
            'hobby': 'varchar(255)',
            'height_': 'int2',
            'weight': 'int',


        }
        # all_altdefs = mg._get_changed_fields(curs, pres)
        # print('\n')
        # for k, v in all_altdefs.items():
        #     sql, msg = _get_alter_column_sql(self, v)
        #     print(msg)
        #     print(sql)
        class User(Model):
            id = Field('SERIAL', sql_onadd='NOT NULL')
            name = Field('varchar(255)')
            profession = Field('varchar(65)')

        mgo = mg.Migration(User, '/home/jahid/Git/Github/neurobin/morm/migration_data')
        print(User.Meta._field_defs_['name'])

        for query, msg, newdata in mgo._migration_query_generator():
            print(msg)
            # print(query)
            # print(newdata)






if __name__ == "__main__":
    unittest.main(verbosity=2)
