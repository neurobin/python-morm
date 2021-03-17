import asyncio
import logging
import unittest
import random
from uuid import uuid4
import inspect

from morm.db import Pool, DB, Transaction
import morm.model as mdl
import morm.meta as mt
import morm.fields.field as fdl
from morm.types import Void
import morm.exceptions as ex


LOGGER_NAME = 'morm-test-field-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_default_funcs(self):
        print("> always_valid returns True all the time")
        self.assertTrue(fdl.always_valid(False) is True)
        print("> nomodifiy returns the exact same value")
        v = 34
        self.assertTrue(v is fdl.nomodify(v))

    def test_Field_Defaults(self):
        f = fdl.Field('varchar(23)')
        print("> Fields default validator is always_valid")
        self.assertTrue(f.validator is fdl.always_valid)
        print("> Fields default modifier is nomodify")
        self.assertTrue(f.modifier is fdl.nomodify)
        print("> Fields default value is Void")
        self.assertTrue(f.default is Void)
        print("> Fields fallback default is False")
        self.assertTrue(f.fallback is False)
        print("> Fields initial value is Void (same as default value)")
        with self.assertRaises(AttributeError):
            self.assertTrue(f.value is Void) # new change

    def test_FieldValue(self):
        v = 45
        f = fdl.FieldValue(fdl.Field("varchar(34)", default='34', validator=lambda x: type(x) is int, modifier=lambda x: int(x)))
        f1 = fdl.FieldValue(fdl.Field("varchar(34)", default='34', validator=lambda x: type(x) is int))
        f2 = fdl.FieldValue(fdl.Field("varchar(34)", default='34', fallback=True, validator=lambda x: type(x) is int))
        print("> default value does not pass through validator")
        self.assertTrue(isinstance(f.value, str))
        with self.assertRaises(ValueError):
            f.value = '454f'

        f.value = '345'

        with self.assertRaises(ValueError):
            f1.value = '34'

        f2.value = '3434' # invalid
        #but fallback is True, so it will not produce exception
        #instead it will be set to default value.
        self.assertTrue(f2.value == '34')
        self.assertTrue(f2.value_change_count == 1)
        f2.value = 3432
        self.assertTrue(f2.value == 3432)
        self.assertTrue(f2.value_change_count == 2)

    def test_ColumnConfig(self):
        cc = fdl.ColumnConfig(sql_engine='mysql', sql_type='int', sql_onadd='', sql_alter=('ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT 1',), sql_ondrop='', column_name='name')
        cc2 = fdl.ColumnConfig(sql_engine='mysql', sql_type='varchar', sql_onadd='NOT NULL', sql_alter=('ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT 0',), sql_ondrop='CASCADE', column_name='old_name')
        self.assertEqual(repr(cc), '''ColumnConfig(sql_engine='mysql', sql_type='int', sql_onadd='', sql_alter=('ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT 1',), sql_ondrop='', column_name='name')''')
        with self.assertRaises(ex.UnsupportedError):
            cc.get_query_column_add('dummy_table')
        with self.assertRaises(ex.UnsupportedError):
            cc.get_query_column_drop('dummy_table')
        with self.assertRaises(ex.UnsupportedError):
            cc.get_query_column_rename('old_name','dummy_table')
        with self.assertRaises(ex.UnsupportedError):
            cc.get_query_column_modify(cc2, 'dummy_table')
        with self.assertRaises(ex.UnsupportedError):
            cc.get_query_column_alter((),'dummy_table')

        cc.conf['sql_engine'] = 'postgresql'
        cc2.conf['sql_engine'] = 'postgresql'
        print(cc.get_query_column_modify(cc2, 'dummy_table'))
        self.assertEqual(
            cc.get_query_column_modify(cc2, 'dummy_table'),
            ('ALTER TABLE "dummy_table" ALTER COLUMN "name" SET DATA TYPE int;\nALTER TABLE "dummy_table" ALTER COLUMN "name" SET DEFAULT 1;', '\n* > MODIFY: old_name: varchar --> int\n* + ALTER TABLE "dummy_table" ALTER COLUMN "name" SET DEFAULT 1')
            )

        cc.conf['sql_alter'] = 'SET SOMETHING'
        with self.assertRaises(TypeError):
            cc.get_query_column_alter(cc2.conf['sql_alter'], 'dummy_table')
        cc.conf['sql_alter'] = ('SET SOMETHING',)
        cc2.conf['sql_alter'] = 'SET SOMETHING'
        with self.assertRaises(TypeError):
            cc.get_query_column_alter(cc2.conf['sql_alter'], 'dummy_table')

        name = fdl.Field('varchar(234)')
        name2 = fdl.Field('varchar(232)')
        self.assertTrue(name != name2)



if __name__ == "__main__":
    unittest.main(verbosity=2)
