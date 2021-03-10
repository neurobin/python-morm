
import asyncio
import unittest
from copy import copy, deepcopy
import pickle
from typing import Dict, List, Tuple, Any
from morm.types import Void, VoidType
import morm.migration as mg
from morm.model import Model, ModelType, Field
from morm.fields.field import ColumnConfig
import os, shutil, sys
from morm.db import DB, Pool, Transaction
import morm.exceptions as ex


class TestMethods(unittest.TestCase):
    migration_path = '/home/jahid/Git/Github/neurobin/morm/migration_data'
    def setUp(self):
        self.DB_POOL = Pool(
            dsn='postgres://',
            host='localhost',
            port=5432,
            user='jahid',
            password='jahid',
            database='test',
            min_size=10,
            max_size=90,
        )

    def tearDown(self):
        # shutil.rmtree(self.migration_path)
        # self.DB_POOL.close() # atexit calls it
        pass


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
            profession = Field('varchar(65)', sql_alter=("SET DEFAULT 'Teacher'",'SET NOT NULL'))

        mgo = mg.Migration(User, '/tmp/..Non-Existent')
        print(' - [x] Field init checks: 1. repr implementation 2. default values')
        self.assertTrue( "Field('varchar(255)', sql_onadd='', sql_ondrop='', sql_alter=(), sql_engine='postgresql'," in repr(User.Meta._field_defs_['name']))

        print(' - [x] Checking pfields and cfields')
        cfields = {'id': ColumnConfig(sql_type='SERIAL', sql_onadd='NOT NULL', sql_ondrop='', sql_alter=(), sql_engine='postgresql', column_name='id'), 'name': ColumnConfig(sql_type='varchar(255)', sql_onadd='', sql_ondrop='', sql_alter=(), sql_engine='postgresql', column_name='name'), 'profession': ColumnConfig(sql_type='varchar(65)', sql_onadd='', sql_ondrop='', sql_alter=("SET DEFAULT 'Teacher'", 'SET NOT NULL'), sql_engine='postgresql', column_name='profession')}
        self.assertTrue(mgo.cfields == cfields)
        self.assertTrue({} == mgo.pfields)

        mgq = mgo._migration_query_generator()

        print(' - [x] Checking add column sql for id')
        query, msg = next(mgq)
        self.assertTrue('''
*******************************************************************************
* > ADD: id: SERIAL

ALTER TABLE "User" ADD COLUMN "id" SERIAL NOT NULL;
*******************************************************************************''' == msg)
        self.assertTrue(query == 'ALTER TABLE "User" ADD COLUMN "id" SERIAL NOT NULL;')

        print(' - [x] Checking add column sql for name')
        query, msg = next(mgq)
        self.assertTrue('''
*******************************************************************************
* > ADD: name: varchar(255)

ALTER TABLE "User" ADD COLUMN "name" varchar(255) ;
*******************************************************************************''' == msg)
        self.assertTrue(query == 'ALTER TABLE "User" ADD COLUMN "name" varchar(255) ;')

        print(' - [x] Checking add column sql for profession')
        query, msg = next(mgq)
        # print(msg)
        self.assertTrue('''
*******************************************************************************
* > ADD: profession: varchar(65)
* + SET DEFAULT 'Teacher'
* + SET NOT NULL

ALTER TABLE "User" ADD COLUMN "profession" varchar(65) ;
ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher', ALTER COLUMN "profession" SET NOT NULL;
*******************************************************************************''' == msg)
        self.assertTrue(query == """ALTER TABLE "User" ADD COLUMN "profession" varchar(65) ;
ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher', ALTER COLUMN "profession" SET NOT NULL;""")

        self.assertEqual(mgo.get_create_table_query(), """
CREATE TABLE "User" (
    "id" SERIAL NOT NULL,
    "name" varchar(255) ,
    "profession" varchar(65) @
);

ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher', ALTER COLUMN "profession" SET NOT NULL;""".replace('@', '').strip())

        mgo = mg.Migration(User, '/home/jahid/Git/Github/neurobin/morm/migration_data')
        mgo.make_migrations(yes=True)

        class User(Model):
            id = Field('SERIAL', sql_onadd='NOT NULL')
            name = Field('varchar(256)')
            profession_name = Field('varchar(265)', sql_alter=("SET DEFAULT 'Teacher'",'SET NOT NULL'))
            hobby = Field('varchar(45)')

        mgpath = '/home/jahid/Git/Github/neurobin/morm/migration_data'
        mgo = mg.Migration(User, mgpath)
        mg.Migration(User, mgpath).make_migrations(yes=True)
        mg.Migration(User, mgpath).make_migrations(yes=True)
        mg.Migration(User, mgpath).make_migrations(yes=True)

        self._migrate(mg.Migration(User, mgpath))
        self._migrate(mg.Migration(User, mgpath))

        mg.Migration(User, mgpath).delete_migration_files(1, 1)

        class AbstractUser(User):
            class Meta:
                abstract = True
        class ProxyUser(User):
            class Meta:
                proxy = True
        with self.assertRaises(ex.MigrationModelNotAllowedError):
            mgo = mg.Migration(AbstractUser, mgpath)

        with self.assertRaises(ex.MigrationModelNotAllowedError):
            mgo = mg.Migration(ProxyUser, mgpath)

        class User(Model):
            id = Field('SERIAL', sql_onadd='NOT NULL')
            name = Field('varchar(25)')
            profession_name = Field('varchar(265)', sql_alter=("SET DEFAULT 'Teacher'",'SET NOT NULL'))
            hobby = Field('varchar(45)')
        sys.argv = [__file__, 'makemigrations', '-y']
        mg.migration_manager(self.DB_POOL, mgpath, [User])
        sys.argv = [__file__, 'migrate']
        mg.migration_manager(self.DB_POOL, mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files', '1', '1']
        mg.migration_manager(self.DB_POOL, mgpath, [User])
        sys.argv = [__file__, 'delete_migration_file', '1', '1']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files', '2', '1']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, mgpath, [User])


    def _migrate(self, mgo: mg.Migration):
        async def _my_migrate():
            async with Transaction(self.DB_POOL) as tdb:
                await mgo.migrate(tdb)
        asyncio.get_event_loop().run_until_complete(_my_migrate())




if __name__ == "__main__":
    unittest.main(verbosity=0)
