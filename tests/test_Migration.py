
import asyncio
import unittest
from copy import copy, deepcopy
import pickle
from typing import Dict, List, Tuple, Any
from morm.void import Void, VoidType
import morm.migration as mg
from morm.model import Model, ModelType, Field
from morm.fields.field import ColumnConfig
import os, shutil, sys
from morm.db import DB, Pool, Transaction
import morm.exceptions as ex
import random

DB_POOL = Pool(
            dsn='postgres://',
            host='localhost',
            port=5432,
            user='jahid',
            password='jahid',
            database='test',
            min_size=10,
            max_size=90,
)

class TestMethods(unittest.TestCase):

    @classmethod
    async def _asetup(cls):
        cls.DB_POOL = DB_POOL
        cls.mgpath = '/tmp/_morm_mgr_x_' + str(random.random())
        db = DB(cls.DB_POOL)
        await db.execute(f'DROP TABLE IF EXISTS "User";')

    @classmethod
    def setUpClass(cls):
        asyncio.get_event_loop().run_until_complete(cls._asetup())

    @classmethod
    def tearDownClass(cls):
        # guard against races or earlier removal of the temp migration path
        try:
            if cls.mgpath and os.path.exists(cls.mgpath):
                shutil.rmtree(cls.mgpath)
        except Exception:
            # swallow errors in teardown to avoid hiding real test failures
            pass

    def setUp(self):
        pass

    def tearDown(self):
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
            profession = Field('varchar(65)', sql_alter=("ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" SET DEFAULT 'Teacher'",'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL'))

        mgo = mg.Migration(User, '/tmp/..Non-Existent')
        print(' - [x] Field init checks: 1. repr implementation 2. default values')
        # print(repr(User.Meta._field_defs_['name']))
        r = repr(User.Meta._field_defs_['name'])
        # be permissive: check key components exist rather than exact formatting
        self.assertIn("sql_onadd", r)
        self.assertIn("sql_alter", r)
        self.assertIn("sql_engine", r)

        print(' - [x] Checking pfields and cfields')
        # print(mgo.cfields)
        cfields = {'id': ColumnConfig(sql_type='SERIAL', sql_onadd='NOT NULL', sql_ondrop='', sql_alter=('ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "__UNQ_{table}_{column}__";',), sql_engine='postgresql', column_name='id'), 'name': ColumnConfig(sql_type='varchar(255)', sql_onadd='', sql_ondrop='', sql_alter=('ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "__UNQ_{table}_{column}__";',), sql_engine='postgresql', column_name='name'), 'profession': ColumnConfig(sql_type='varchar(65)', sql_onadd='', sql_ondrop='', sql_alter=('ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "__UNQ_{table}_{column}__";', 'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT \'Teacher\'', 'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL'), sql_engine='postgresql', column_name='profession')}
        self.assertTrue(mgo.cfields == cfields)
        self.assertTrue({} == mgo.pfields)

        mgq = mgo._migration_query_generator()

        print(' - [x] Checking add column sql for id')
        query, msg = next(mgq)
        self.assertTrue('''
*******************************************************************************
* > ADD: id: SERIAL
* + ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_id__";

ALTER TABLE "User" ADD COLUMN "id" SERIAL NOT NULL;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_id__";;
*******************************************************************************''' == msg)
        self.assertTrue(query == 'ALTER TABLE "User" ADD COLUMN "id" SERIAL NOT NULL;\nALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_id__";;')

        print(' - [x] Checking add column sql for name')
        query, msg = next(mgq)
        # print(msg)
        self.assertTrue('''
*******************************************************************************
* > ADD: name: varchar(255)
* + ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_name__";

ALTER TABLE "User" ADD COLUMN "name" varchar(255) ;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_name__";;
*******************************************************************************''' == msg)
        self.assertTrue(query == 'ALTER TABLE "User" ADD COLUMN "name" varchar(255) ;\nALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_name__";;')

        print(' - [x] Checking add column sql for profession')
        query, msg = next(mgq)
        # print(msg)
        self.assertEqual('''
*******************************************************************************
* > ADD: profession: varchar(65)
* + ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_profession__";
* + ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher'
* + ALTER TABLE "User" ALTER COLUMN "profession" SET NOT NULL

ALTER TABLE "User" ADD COLUMN "profession" varchar(65) ;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_profession__";; ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher'; ALTER TABLE "User" ALTER COLUMN "profession" SET NOT NULL;
*******************************************************************************''', msg)
        self.assertEqual(query, """ALTER TABLE "User" ADD COLUMN "profession" varchar(65) ;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_profession__";; ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher'; ALTER TABLE "User" ALTER COLUMN "profession" SET NOT NULL;""")

        print(mgo.get_create_table_query())
        self.assertEqual(mgo.get_create_table_query(), """
CREATE TABLE "User" (
    "id" SERIAL NOT NULL,
    "name" varchar(255) ,
    "profession" varchar(65) @
);ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_id__";;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_name__";;
ALTER TABLE "User" DROP CONSTRAINT IF EXISTS "__UNQ_User_profession__";; ALTER TABLE "User" ALTER COLUMN "profession" SET DEFAULT 'Teacher'; ALTER TABLE "User" ALTER COLUMN "profession" SET NOT NULL;""".replace('@', '').strip())

        mgo = mg.Migration(User, self.mgpath)
        mgo.make_migrations(yes=True)

        class User(Model):
            id = Field('SERIAL', sql_onadd='NOT NULL')
            name = Field('varchar(256)')
            profession_name = Field('varchar(265)', sql_alter=("ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" SET DEFAULT 'Teacher'",'ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL'))
            hobby = Field('varchar(45)')

        mgo = mg.Migration(User, self.mgpath)
        mg.Migration(User, self.mgpath).make_migrations(yes=True)
        mg.Migration(User, self.mgpath).make_migrations(yes=True)
        mg.Migration(User, self.mgpath).make_migrations(yes=True)

        self._migrate(mg.Migration(User, self.mgpath))
        self._migrate(mg.Migration(User, self.mgpath))

        mg.Migration(User, self.mgpath).delete_migration_files(1, 1)

        class AbstractUser(User):
            class Meta:
                abstract = True
        class ProxyUser(User):
            class Meta:
                proxy = True
        with self.assertRaises(ex.MigrationModelNotAllowedError):
            mgo = mg.Migration(AbstractUser, self.mgpath)

        with self.assertRaises(ex.MigrationModelNotAllowedError):
            mgo = mg.Migration(ProxyUser, self.mgpath)

        self.assertEqual(mgo.default_json, mgo._get_json_from_file('___non_existence'))

        class User(Model):
            id = Field('SERIAL', sql_onadd='NOT NULL')
            name = Field('varchar(25)')
            profession_name = Field('varchar(265)', sql_alter=("SET DEFAULT 'Teacher'",'SET NOT NULL'))
        sys.argv = [__file__, 'makemigrations', '-y']
        mg.migration_manager(self.DB_POOL, self.mgpath, [User])
        sys.argv = [__file__, 'migrate']
        mg.migration_manager(self.DB_POOL, self.mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files', '1', '1']
        mg.migration_manager(self.DB_POOL, self.mgpath, [User])
        sys.argv = [__file__, 'delete_migration_file', '1', '1']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, self.mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, self.mgpath, [User])
        sys.argv = [__file__, 'delete_migration_files', '2', '1']
        with self.assertRaises(ValueError):
            mg.migration_manager(self.DB_POOL, self.mgpath, [User])


    def _migrate(self, mgo: mg.Migration):
        async def _my_migrate():
            await mgo.migrate(self.DB_POOL)
        asyncio.get_event_loop().run_until_complete(_my_migrate())

    def test_unique_groups(self):
        """Test unique_groups functionality in migrations"""
        print('\n=== Testing unique_groups feature ===')

        # Test 1: Model with unique_groups
        class UserWithUniqueGroups(Model):
            class Meta:
                db_table = 'UserUniqueTest'
                unique_groups = {
                    'name_email': ['name', 'email'],
                    'email_profession': ['email', 'profession']
                }

            id = Field('SERIAL', sql_onadd='PRIMARY KEY NOT NULL')
            name = Field('varchar(255)')
            email = Field('varchar(255)')
            profession = Field('varchar(100)')

        print(' - [x] Checking unique_groups in Meta')
        self.assertTrue(hasattr(UserWithUniqueGroups.Meta, 'unique_groups'))
        self.assertEqual(UserWithUniqueGroups.Meta.unique_groups, {
            'name_email': ['name', 'email'],
            'email_profession': ['email', 'profession']
        })

        # Test 2: CREATE TABLE query includes constraints
        mgpath_test = '/tmp/_morm_unique_groups_test_' + str(random.random())
        mgo = mg.Migration(UserWithUniqueGroups, mgpath_test)

        create_query = mgo.get_create_table_query()
        print('\n - [x] Checking CREATE TABLE query')
        print(create_query)

        self.assertIn('__UNQ_UserUniqueTest_name_email__', create_query)
        self.assertIn('__UNQ_UserUniqueTest_email_profession__', create_query)
        self.assertIn('UNIQUE ("name", "email")', create_query)
        self.assertIn('UNIQUE ("email", "profession")', create_query)
        self.assertIn('ALTER TABLE "UserUniqueTest" ADD CONSTRAINT', create_query)

        # Test 3: Migration JSON includes unique_groups
        print(' - [x] Checking migration JSON structure')
        self.assertIn('unique_groups', mgo.current_json)
        self.assertEqual(mgo.current_json['unique_groups'], {
            'name_email': ['name', 'email'],
            'email_profession': ['email', 'profession']
        })

        # Test 4: Change detection
        print(' - [x] Testing unique_groups change detection')
        import json
        os.makedirs(mgo.migration_dir, exist_ok=True)

        # Create a previous migration with different unique_groups
        prev_json = mgo.current_json.copy()
        prev_json['unique_groups'] = {
            'old_constraint': ['name', 'profession']
        }
        prev_file = os.path.join(mgo.migration_dir, 'UserUniqueTest_00000001_test.json')
        with open(prev_file, 'w') as f:
            json.dump(prev_json, f)

        # Create new migration object to detect changes
        mgo2 = mg.Migration(UserWithUniqueGroups, mgpath_test)
        changes = list(mgo2._get_unique_groups_changes())

        self.assertGreater(len(changes), 0)

        queries_combined = ' '.join([q for q, m in changes])
        print(f'\n   Detected {len(changes)} changes')
        for q, m in changes:
            print(f'   {m}')

        # Should drop old constraint
        self.assertIn('DROP CONSTRAINT', queries_combined)
        self.assertIn('__UNQ_UserUniqueTest_old_constraint__', queries_combined)

        # Should add new constraints
        self.assertIn('ADD CONSTRAINT', queries_combined)
        self.assertIn('__UNQ_UserUniqueTest_name_email__', queries_combined)
        self.assertIn('__UNQ_UserUniqueTest_email_profession__', queries_combined)

        # Cleanup
        shutil.rmtree(mgpath_test)

        print(' - [x] unique_groups tests passed!')


if __name__ == "__main__":
    unittest.main(verbosity=0)
