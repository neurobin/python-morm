import asyncio
import logging
import unittest
import random
from uuid import uuid4
import inspect

from morm.db import Pool, DB, Transaction
import morm.model as mdl
import morm.meta as mt
from morm.types import Void


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

from morm import Field
# from morm.model import ModelBase as Model
from morm.model import Model

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
    hobby = Field('varchar(255)')
    status = Field('varchar(255)')
    salary = Field('varchar(255)')

    class Meta:
        ordering = ('name', '-profession', '+age')
        exclude_fields_down = ('age',)
        exclude_values_down = {
            '': (Void,),
            'profession': ('developer',)
            }

class BigUser2(Model):
    id = Field('SERIAL NOT NULL')
    name = Field('varchar(255)')
    profession = Field('varchar(255)')
    age = Field("int")
    hobby = Field('varchar(255)')
    status = Field('varchar(255)')
    salary = Field('varchar(255)')

    class Meta:
        fields_down = ('id', 'name', 'profession')
        exclude_values_down = {
            '': ('developer',)
            }


class TestMethods(unittest.TestCase):

    def test_Model_Instance(self):
        b = BigUser(name='__dummy__', age=23)

    async def _test_transaction_setup(self):
        b = BigUser(name='__dummy__', age=23)
        # await b._save_()

    async def _test_direct_execute(self):
        await SNORM_DB_POOL.pool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')

    async def _test_transaction(self):
        try:
            async with Transaction(SNORM_DB_POOL) as con:
                # b = await BigUser._get_(where="name='__dummy__'", con=con)
                # b.age += 2
                # await b._save_(con=con)
                # # raise Exception
                await con.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
        except:
            raise
        # b = await BigUser._get_(where="name='__dummy__'")
        # self.assertEqual(b.age, 23)
        pass

    def clean(self):
        SNORM_DB_POOL.close()

    def test_transaction(self):
        try:
            asyncio.get_event_loop().run_until_complete(self._test_transaction_setup())
            # group = asyncio.gather(self._test_transaction_setup(), *[self._test_transaction() for i in range(10)])
            # group = asyncio.gather( *[self._test_transaction() for i in range(10000)])
            group = asyncio.gather( *[self._test_direct_execute() for i in range(10)])
            # group = asyncio.gather(self._test_transaction_setup())
            asyncio.get_event_loop().run_until_complete(asyncio.gather(group))
        finally:
            self.clean()

    async def _test_db_filter_data(self):
        db = DB(SNORM_DB_POOL)
        mq = db(BigUser).filter().qc('', '$1', True)
        mq2 = db(BigUser2).filter().qc('', '$1', True)
        mqq = ' SELECT "name","profession","hobby","status","salary" FROM "BigUser" WHERE $1 ORDER BY "name" ASC,"profession" DESC,"age" DESC'
        mqq2 = ' SELECT "id","name","profession" FROM "BigUser2" WHERE $1 '
        print(mq2.qget())
        res = await mq.fetch()
        res2 = await mq2.fetch()
        big_user1 = await db(BigUser2).get(2)
        self.assertEqual(big_user1.id, 2)
        print(res)
        print(res2)
        print(big_user1)
        big_user3 = await db(BigUser2).get('dev', col='profession')
        self.assertEqual(big_user3.profession, 'dev')
        print(big_user3)
        print('\n## Exclude fields and values\n')

        print('* fields_down and exclude_fields_down control which fields will be retrieved from db and accessed from model object')
        self.assertEqual(mq.qget()[0], mqq)
        self.assertEqual(mq2.qget()[0], mqq2)
        print('* keys excluded for down with field name can not be accessed')
        with self.assertRaises(AttributeError):
            res[0].age
        print('* keys excluded for down with values can not be accessed')
        with self.assertRaises(AttributeError):
            res[0].profesion

        print('* when fields_down is specified, only specified fields will be down')
        with self.assertRaises(AttributeError):
            res2[0].profession # developer is in exclude_values_down
        res2[0].name
        print('* when fields_down is specified, unspecified fields will not be accessible')
        with self.assertRaises(AttributeError):
            res2[0].age
        with self.assertRaises(AttributeError):
            res2[0].salary
        with self.assertRaises(AttributeError):
            res2[0].hobby
        with self.assertRaises(AttributeError):
            res2[0].status


    def test_filter_func(self):
        db = DB(SNORM_DB_POOL)
        q = db(BigUser).filter().qc('', '$1', True).qget()
        print(q)
        asyncio.get_event_loop().run_until_complete(self._test_db_filter_data())

    def test_q_qq(self):
        db = DB(SNORM_DB_POOL)
        buq = db(BigUser2)
        self.assertEqual(buq.q(
            f'SELECT * FROM {buq.table} WHERE {buq.pk}=$1 AND "{buq.fn.profession}" = :profession', 2, profession='developer').qget(),
            (' SELECT * FROM BigUser2 WHERE id=$1 AND "profession" = $2 ', [2, 'developer'])
        )

        print('* Misspelling will produce AttributeError')
        with self.assertRaises(AttributeError):
            buq\
                .q(f'SELECT * FROM {buq.table} WHERE {buq.pk}=$1 AND "{buq.fn.profesion}" = :profession', 2, profession='developer')\
                .qget()

        self.assertEqual(
            buq.reset()\
                .q(f'SELECT')\
                .qq('age')\
                .q(f', "{buq.fn.profession}", "{buq.fn.hobby}", "{buq.fn.status}"')\
                .q(f'FROM {buq.table} WHERE')\
                .q(f'"{buq.fn.age}" >= ${buq.c} AND "{buq.fn.status}" = :status', 13, status='OK')\
                #fdsfd
                .q(f'AND status=:status')\
                .q(f'AND hobby=${buq.c}', 'gardening', hobby='Teaching')\
                .q(f'AND "{buq.fn.salary}"=:status')\
                .q(f'AND "{buq.fn.hobby}"=:hobby')\
                .qget(),
            (' SELECT "age" , "profession", "hobby", "status" FROM BigUser2 WHERE "age" >= $1 AND "status" = $2 AND status=$2 AND hobby=$3 AND "salary"=$2 AND "hobby"=$4 ', [13, 'OK', 'gardening', 'Teaching'])
        )


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