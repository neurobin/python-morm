import asyncio
import logging
import unittest
import random
from uuid import uuid4
import inspect

from morm.db import Pool, DB, Transaction
import morm.model as mdl
import morm.meta as mt


LOGGER_NAME = 'morm-test-model-'
log = logging.getLogger(LOGGER_NAME)

def get_file_content(path):
    cont = ''
    try:
        with open(path, 'r') as f:
            cont = f.read();
    except Exception as e:
        log.exception("E: could not read file: " + path)
    return cont


SNORM_DB_POOL = Pool(
    dsn='postgres://',
    host='localhost',
    port=5432,
    user='jahid',
    password='jahid',
    database='test',
    min_size=10,
    max_size=90,
)

from morm import Model, Field

def mprint(*args, **kwargs):
    print("-"*80)
    print(*args, **kwargs)
    print("-"*80)


class User(Model):
    name = Field('varchar(255)')
    profession = Field('varchar(255)')

class BigUser(Model):
    name = Field('varchar(255)')
    profession = Field('varchar(255)')
    age = Field("int")

class BigUser2(Model):
    name = Field('varchar(255)')
    profession = Field('varchar(255)')
    age = Field("int")


class TestMethods(unittest.TestCase):

    def test_Model_Instance(self):
        b = BigUser(name='__dummy__', age=23)

    async def _test_transaction_setup(self):
        b = BigUser(name='__dummy__', age=23)
        # await b._save_()

    async def _test_transaction(self):
        try:
            async with Transaction(BigUser._db_) as con:
                # b = await BigUser._get_(where="name='__dummy__'", con=con)
                # b.age += 2
                # await b._save_(con=con)
                # # raise Exception
                await con.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
        except:
            pass
        # b = await BigUser._get_(where="name='__dummy__'")
        # self.assertEqual(b.age, 23)
        pass

    def clean(self):
        SNORM_DB_POOL.close()

    def test_transaction(self):
        try:
            asyncio.get_event_loop().run_until_complete(self._test_transaction_setup())
            # group = asyncio.gather(self._test_transaction_setup(), *[self._test_transaction() for i in range(10)])
            group = asyncio.gather( *[self._test_transaction() for i in range(10)])
            # group = asyncio.gather(self._test_transaction_setup())
            asyncio.get_event_loop().run_until_complete(asyncio.gather(group))
        finally:
            self.clean()

    # def _test_something(self):
    #     db = DB(SNORM_DB_POOL)
    #     dbpool = await db.pool()
    #     await dbpool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
    #     # await db.execute('INSERT into test_table')
    #     mos = await test_table._get_(where='name like $1 order by id asc', prepared_args=['%dumm%'])
    #     print(mos.__dict__)
    #     # print(mos[0].__dict__)
    #     print(BigUser()._fields_)
    #     print(BigUser._get_table_name_())
    #     b = BigUser()
    #     b.name = 'jahid'
    #     b.age = 28
    #     print(b._get_insert_query_())
    #     id = await b._insert_()
    #     print(id)

    #     b1 = await BigUser._get_(where='id=1')
    #     b1.name = 'Jahidul Hamid'
    #     print(b1._get_update_query_())
    #     await b1._update_()
    #     b = BigUser()
    #     b.name = 'John Doeee'
    #     b.profession = 'Teacher'
    #     await b._save_()
    #     b.age = 34
    #     await b._save_()
    #     d = {
    #         'name': 'John Doe',
    #         'age': 45,
    #     }
    #     b = BigUser(name='Jahid')


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    except:
        SNORM_DB_POOL.close()
        raise
