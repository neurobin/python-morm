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
        print('## CRUD methods\n')
        db = DB(SNORM_DB_POOL)
        mq = db(BigUser).qfilter().qc('', '$1', True)
        mq2 = db(BigUser2).qfilter().qc('', '$1', True)
        mqq = ' SELECT "name","profession","hobby","status","salary" FROM "BigUser" WHERE $1 ORDER BY "name" ASC,"profession" DESC,"age" DESC'
        mqq2 = ' SELECT "id","name","profession" FROM "BigUser2" WHERE $1 '
        res = await mq.fetch()
        res2 = await mq2.fetch()
        big_user1 = await db(BigUser2).get(2)
        print(f' - [x] Check get by pk')
        self.assertEqual(big_user1.id, 2)
        big_user3 = await db(BigUser2).get('dev', col='profession')
        print(f' - [x] Check get by arbitrary column')
        self.assertEqual(big_user3.profession, 'dev')
        print('\n### Exclude fields and values\n')

        print('* fields_down and exclude_fields_down control which fields will be retrieved from db and accessed from model object')
        self.assertEqual(mq.getq()[0], mqq)
        self.assertEqual(mq2.getq()[0], mqq2)
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

        user5 = BigUser2(name='Jahidul Hamid', age=31)
        print(f' - [x] model object can not be mistaken as model in db() call')
        with self.assertRaises(TypeError):
            db(user5)
        print(f' - [x] get_insert_query is OK')
        self.assertEqual(
            db.get_insert_query(user5),
            ('INSERT INTO "BigUser2" ("name","age") VALUES ($1, $2) RETURNING "id"', ['Jahidul Hamid', 31])
        )
        # print(await db(user5).insert())
        user6 = await db(BigUser2).get(6)
        user6.hobby = 'something4'
        # user6.hobby = 'something2'
        # print(db(user6).get_update_query())
        # print(db(user6).get_update_query())
        print(f' - [x] Check save() calls update() and they are ok')
        self.assertEqual(
            await db.save(user6),
            'UPDATE 1'
        )
        usern = BigUser2(name='dummy john', profession='Student', age=23, hobby='collection', salary='0')
        print(f' - [x] Check save()')
        self.assertTrue(await db.save(usern) > 0)

        print(f'\n# Checking db(Model).update() method\n')
        f = BigUser2.Meta.f
        data = {
            f.name: 'John Doe',
            f.profession: 'Student',
            f.age: 23,
            f.hobby: 'gardenning',
        }
        # db.q(BigUser2).q_()


    def test_filter_func(self):
        db = DB(SNORM_DB_POOL)
        q = db(BigUser).qfilter().qc('', '$1', True).getq()
        self.assertEqual(
            q,
            (' SELECT "name","profession","hobby","status","salary" FROM "BigUser" WHERE $1 ORDER BY "name" ASC,"profession" DESC,"age" DESC', [True])
        )
        asyncio.get_event_loop().run_until_complete(self._test_db_filter_data())

    def test_q_qq(self):
        db = DB(SNORM_DB_POOL)
        buq = db(BigUser2)
        self.assertEqual(buq.q_(
            f'SELECT * FROM {buq.db_table} WHERE {buq.pk}=$1 AND {buq.f.profession} = :profession', 2, profession='developer').getq(),
            (' SELECT * FROM "BigUser2" WHERE "id"=$1 AND "profession" = $2 ', [2, 'developer'])
        )

        print('* Misspelling will produce AttributeError')
        with self.assertRaises(AttributeError):
            buq\
                .q_(f'SELECT * FROM {buq.db_table} WHERE {buq.pk}=$1 AND "{buq.f.profesion}" = :profession', 2, profession='developer')\
                .getq()

        self.assertEqual(
            buq.reset()\
                .q(f'SELECT')\
                .qq('age')\
                .q(f', {buq.f.profession}, {buq.f.hobby}, {buq.f.status}')\
                .q(f'FROM {buq.db_table} WHERE')\
                .q_(f'{buq.f.age} >= ${buq.c} AND {buq.f.status} = :status', 13, status='OK')\
                #fdsfd
                .q_(f'AND status=:status')\
                .q_(f'AND hobby=${buq.c}', 'gardening', hobby='Teaching')\
                .q_(f'AND {buq.f.salary}=:status')\
                .q_(f'AND {buq.f.hobby}=:hobby')\
                .getq(),
            (' SELECT "age" , "profession", "hobby", "status" FROM "BigUser2" WHERE "age" >= $1 AND "status" = $2 AND status=$2 AND hobby=$3 AND "salary"=$2 AND "hobby"=$4 ', [13, 'OK', 'gardening', 'Teaching'])
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
        unittest.main(verbosity=0)
    except:
        SNORM_DB_POOL.close()
        raise
