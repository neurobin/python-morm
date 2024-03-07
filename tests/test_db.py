import asyncio
import logging
import unittest
import random
from uuid import uuid4
import inspect
import asyncpg # type: ignore
import sys, shutil

from morm.db import Pool, DB, Transaction, ModelQuery
import morm.model as mdl
import morm.meta as mt
from morm.void import Void
from morm.fields import Field
# from morm.model import ModelBase as Model
from morm.model import Model
from morm.pg_models import Base, BaseCommon
import morm.migration as mg
import random


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


def mprint(*args, **kwargs):
    print("-"*80)
    print(*args, **kwargs)
    print("-"*80)


class User(Model):
    name = Field('varchar(255)')
    profession = Field('varchar(255)')

class BigUser(Model):
    id = Field('SERIAL NOT NULL')
    name = Field('varchar(255)')
    profession = Field('varchar(255)')
    age = Field("integer")
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
    age = Field("integer")
    hobby = Field('varchar(255)')
    status = Field('varchar(255)')
    salary = Field('varchar(255)')

    class Meta:
        fields_down = ('id', 'name', 'profession')
        exclude_values_down = {
            '': ('developer',),
            'profession': (None,),
            }


class TestMethods(unittest.TestCase):

    @classmethod
    async def _asetup(cls):
        db = DB(SNORM_DB_POOL)
        cls.mgr_base_path = '/tmp/__morm_migration__x_' + str(random.random())
        await db.execute(f'DROP TABLE IF EXISTS "{BigUser.Meta.db_table}"; DROP TABLE IF EXISTS "{BigUser2.Meta.db_table}";')
        models = [BigUser, BigUser2]
        for model in models:
            mgo = mg.Migration(model, cls.mgr_base_path)
            mgo.make_migrations(yes=True)
            await mgo.migrate(SNORM_DB_POOL)
        users = [
            {'name': 'Jahid', 'profession': 'developer'},
            {'name': 'John', 'profession': 'dev'}, # this needs to be in second position
            {'name': 'John Doe', 'profession': 'Teacher'},
            {'name': 'Jane Doe', 'profession': 'Teacher'},
            {'name': 'John Doe', 'profession': 'Teacher'},
            {'name': 'Jane Doe', 'profession': 'Teacher'},
        ]
        # input('Enter to continue')
        for user in users:
            u1 = BigUser(user)
            u2 = BigUser2(user)
            await db.save(u1)
            await db.save(u2)

    @classmethod
    def setUpClass(cls):
        asyncio.get_event_loop().run_until_complete(cls._asetup())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.mgr_base_path)


    def test_Model_Instance(self):
        b = BigUser(name='__dummy__', age=23)

    async def _test_transaction_setup(self):
        b = BigUser(name='__dummy__', age=23)
        # await b._save_()

    async def _test_direct_execute(self):
        await SNORM_DB_POOL.pool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')

    async def _test_transaction(self):
        try:
            tr = Transaction(SNORM_DB_POOL)
            async with tr as tdb:
                # b = await BigUser._get_(where="name='__dummy__'", con=con)
                # b.age += 2
                # await b._save_(con=con)
                # # raise Exception
                await tdb.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
                record = await tdb.fetch('SELECT * FROM "BigUser" where "id"=0')
                self.assertEqual(record, [])
                record = await tdb.fetchrow('SELECT * FROM "BigUser" where "id"=0')
                self.assertEqual(record, None)
                record = await tdb.q(BigUser).q('SELECT * FROM "BigUser" where "id"=0').fetchrow()
                self.assertEqual(record, None)
            try:
                async with tr as tdb:
                    print('- [x] Checking transaction rollback')
                    await tdb.execute('''INSERT INTO "BigUser" ("name", "profession") VALUES ('John Doe', 'Teacher')''')
                    await tdb.execute('''SELECT * FROM "BigUser" WHERE "name"='John Doe', ''') # wrong sql
            except asyncpg.exceptions.PostgresSyntaxError:
                pass
        except:
            raise
        # b = await BigUser._get_(where="name='__dummy__'")
        # self.assertEqual(b.age, 23)
        pass

    def clean(self):
        # SNORM_DB_POOL.close() # atexit calls it
        pass

    def test_transaction(self):
        try:
            asyncio.get_event_loop().run_until_complete(self._test_transaction_setup())
            asyncio.get_event_loop().run_until_complete(self._test_transaction())
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
        mq = db(BigUser).qfilter().qc('', '$1', True) # this one has ordering
        mq2 = db(BigUser2).qfilter(no_ordering=True).qc('', '$1', True).qorder().qo('id')
        # print(mq.getq())
        mqq = ' SELECT "id","name","profession","hobby","status","salary" FROM "BigUser" WHERE $1 ORDER BY "name" ASC,"profession" DESC,"age" DESC'
        mqq2 = ' SELECT "id","name","profession" FROM "BigUser2" WHERE $1 ORDER BY "id" ASC '
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
        # print(mq.getq()[0])
        self.assertEqual(mq.getq()[0], mqq)
        self.assertEqual(mq2.getq()[0], mqq2)
        print('* keys excluded for down with field name can not be accessed')
        with self.assertRaises(AttributeError):
            res[0].age
        print('* keys excluded for down with values can not be accessed')
        with self.assertRaises(AttributeError):
            res[0].profesion

        print('* when fields_down is specified, only specified fields will be down')
        # print(res2[0])
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
        print(f' - [x] Check only updated fields are included in update.')
        self.assertEqual(db.get_update_query(user6), ('UPDATE "BigUser2" SET "hobby"=$1 WHERE "id"=$2', ['something4', 6]))
        print(f' - [x] Check save() calls update() and they are ok')
        self.assertEqual(
            await db.save(user6),
            'UPDATE 1'
        )
        print(f' - [x] Check: once update is done, change counters are reset.')
        self.assertEqual(db.get_update_query(user6), ('', []))
        db.get_update_query(user6)
        usern = BigUser2(name='dummy john', profession='Student', age=23, hobby='collection', salary='0')
        print(f' - [x] Check save()')
        self.assertTrue(await db.save(usern) > 0)
        self.assertEqual(await db.update(usern), db.DATA_NO_CHANGE)
        mdq = db(BigUser2)
        self.assertIn(ModelQuery.__name__, repr(mdq))
        self.assertEqual(
            mdq.qc_('status', f'= :status and "age" = ${mdq.c}', 23, status='OK').getq(),
            (' "status" = $2 and "age" = $1 ', [23, 'OK']))
        self.assertEqual(
            mdq.reset().qo('-name,').qo('+age').getq(),
            (' "name" DESC, "age" ASC ', []))
        self.assertEqual(
            mdq.reset().qu({'name': 'John', 'age': 29}).getq(),
            (' "name"=$1, "age"=$2 ', ['John', 29]))
        self.assertEqual(
            mdq.reset().qreturning('name', 'age').getq(),
            (' RETURNING "name","age" ', []))
        self.assertEqual(
            mdq.reset().qwhere().getq(),
            (' WHERE ', []))

        with self.assertRaises(ValueError):
            print(mdq.reset().qfilter().qfilter().getq())

        self.assertEqual(
            mdq.reset().qupdate({'name': 'John', 'age': 29}).getq(),
            (' UPDATE "BigUser2" SET "name"=$1, "age"=$2 WHERE ', ['John', 29]))

        with self.assertRaises(ValueError):
            mdq.reset().qupdate({'name': 'John', 'age': 29}).qupdate({'name': 'John', 'age': 29})

        q = mdq.reset().qupdate({'name': 'John', 'age': 29}).q(f'"id"=1').qreturning('name')
        self.assertEqual(q.getq(), (' UPDATE "BigUser2" SET "name"=$1, "age"=$2 WHERE "id"=1 RETURNING "name" ', ['John', 29]))
        name1 = await q.fetchval()
        user1 = await mdq.get(1)
        self.assertEqual(name1, user1.name)

        print(f'\n# Checking db(Model).update() method\n')
        f = BigUser2.Meta.f
        data = {
            f.name: 'John Doe',
            f.profession: 'Student',
            f.age: 23,
            f.hobby: 'gardenning',
        }
        print(f' - [x] Checking field name access from Model.Meta.f')
        self.assertTrue(f.profession == 'profession')
        with self.assertRaises(AttributeError):
            f.profesion

        print(f'* Changing Model.Meta.f.<field_name> is not possible.')
        with self.assertRaises(NotImplementedError):
            f.profession = 343

        # db.q(BigUser2).q_()
        class BigUser3(Model):pass
        self.assertEqual(db.get_insert_query(BigUser3()), ('', []))
        class BigUser3(Base):pass
        b = BigUser3()
        b.id = 3
        self.assertEqual(db.get_update_query(b), ('', []))

        # delete check
        user5 = await db(BigUser2).get(5)
        self.assertEqual(user5.id, 5)
        await db.delete(user5)
        user5 = await db(BigUser2).get(5)
        self.assertEqual(user5, None)


    def test_filter_func(self):
        db = DB(SNORM_DB_POOL)
        q = db(BigUser).qfilter().qc('', '$1', True).getq()
        # print(q)
        self.assertEqual(
            q,
            (' SELECT "id","name","profession","hobby","status","salary" FROM "BigUser" WHERE $1 ORDER BY "name" ASC,"profession" DESC,"age" DESC', [True])
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
    #     mos = await test_table._get_(where='name like $1 order by id asc', args=['%dumm%'])
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
        SNORM_DB_POOL._close() # at exit calls it, we do not need to call it explicitly. It is called here for coverage report
        raise
