import asyncio
import logging
import unittest
import random
from uuid import uuid4
import inspect

from morm.db import Pool, DB, Transaction
import morm.model as mdl
import morm.meta as mt


LOGGER_NAME = 'morm-'
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

class TestMethods(unittest.TestCase):

    def checkModelAttributeSet(self, name, value):
        print(f"> Checking attribute '{name}' with invalid value {value} for model class")
        class User(Model):pass
        setattr(User, name, value)


    def checkModelAttributeDel(self, name):
        print(f"> Checking attribute '{name}' for deletion for model class")
        class User(Model):pass
        delattr(User, name)

    def checkMetaAttributeSet(self, name, value):
        print(f"> Checking attribute '{name}' with invalid value {value} for Meta class of model")
        class User(Model):
            class Meta(mdl.Meta): pass
            setattr(Meta, name, value)

    def checkMetaAttributeDel(self, name, value):
        print(f"> Checking attribute '{name}' for deletion for Meta class of model")
        class User(Model):
            class Meta(mdl.Meta): pass
            delattr(Meta, name)

    def test_Model_Attr_Set_Del(self):
        attrs = ['Meta', 'name', 'dummy', 'hozoborolo']
        for k in attrs:
            with self.assertRaises(NotImplementedError):
                self.checkModelAttributeSet(k, 32)
            with self.assertRaises(NotImplementedError):
                self.checkModelAttributeDel(k)

    def test_Model_Meta(self):
        with self.assertRaises(TypeError):
            class User(Model):
                Meta = 32

    def test_Model_Internal_Meta(self):
        def checkTypeError(attr, value):
            with self.assertRaises(TypeError):
                class User(Model):
                    class Meta(mdl.Meta):pass
                    setattr(Meta, attr, value)
        with self.assertRaises(ValueError):
            class User(Model):
                class Meta(mdl.Meta):
                    _field_defs_ = 67576

    def test_Model_Meta_Attr_Set_Del(self):

        meta_attrs = {
            'pk': 23,
            'proxy': 23,             # TODO: Implement in migration
            'ordering': 23,             # TODO: Implement in db util
            'fields_up': 23,            # TODO: Implement in db util
            'fields_down': 23,          # TODO: Implement in db util
            'exclude_up_keys': 23,      # TODO: Implement in db util
            'exclude_down_keys': 23,    # TODO: Implement in db util
            'exclude_up_values': 23,    # TODO: Implement in db util
            'exclude_down_values': 23,  # TODO: Implement in db util
            'db_table': 23,
            'abstract': 23,          # TODO: Implement in migration
        }

        for k, v in meta_attrs.items():
            with self.assertRaises(NotImplementedError):
                self.checkMetaAttributeSet(k, v)
            with self.assertRaises(NotImplementedError):
                self.checkMetaAttributeDel(k, v)

    def checkMetaAttributeType(self, name, value):
        print(f"> Checking attribute '{name}' with invalid value {value} for Meta class in Model")
        class User(Model):
            Meta = mt.MetaType('Meta', (mt.Meta,), {name: value})

    def test_Model_Meta_Attr_Types(self):

        meta_attrs = {
            'pk': 23,
            'proxy': 23,             # TODO: Implement in migration
            'ordering': 23,             # TODO: Implement in db util
            'fields_up': 23,            # TODO: Implement in db util
            'fields_down': 23,          # TODO: Implement in db util
            'exclude_up_keys': 23,      # TODO: Implement in db util
            'exclude_down_keys': 23,    # TODO: Implement in db util
            'exclude_up_values': 23,    # TODO: Implement in db util
            'exclude_down_values': 23,  # TODO: Implement in db util
            'db_table': 23,
            'abstract': 23,          # TODO: Implement in migration
        }

        for k, v in meta_attrs.items():
            with self.assertRaises(TypeError):
                self.checkMetaAttributeType(k, v)

    def test_Model_Meta_Attr_Defaults(self):
        class User(Model):
            profession = Field('varchar(255)')
            name = Field('varchar(255)')
        class BigUser(User):
            age = Field("int")

        self.assertEqual(User.Meta.db_table, 'User')
        self.assertEqual(BigUser.Meta.db_table, 'BigUser')
        self.assertTrue(User.Meta._field_defs_)
        mprint(User.Meta._field_defs_)
        mprint(type(User.Meta._field_defs_))


        # with self.assertRaises(TypeError):
        #     class User(Model):
        #         class Meta(mdl.Meta):
        #             pk = 23
        # with self.assertRaises(TypeError):
        #     class User(Model):
        #         class Meta(mdl.Meta):
        #             proxy = 23
        # with self.assertRaises(TypeError):
        #     class User(Model):
        #         class Meta(mdl.Meta):
        #             ordering = 23
        # with self.assertRaises(TypeError):
        #     class User(Model):
        #         class Meta(mdl.Meta):
        #             ordering = 23



    def test_Model_Instance(self):
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

        user = BigUser()
        user.name = 'ffdsf'
        user.age = 34
        user.profession = 'Teacher'
        with self.assertRaises(AttributeError):
            user.profesion = 'Teacher' # spelling mistake
        mprint(inspect.getsource(BigUser2))
        mprint(user)

        # b = BigUser(name='__dummy__', age=23)

    # async def _test_transaction_setup(self):
    #     b = BigUser(name='__dummy__', age=23)
    #     # await b._save_()

    # async def _test_transaction(self):
    #     # try:
    #     #     async with Transaction(BigUser._db_) as con:
    #     #         b = await BigUser._get_(where="name='__dummy__'", con=con)
    #     #         b.age += 2
    #     #         await b._save_(con=con)
    #     #         # raise Exception
    #     # except:
    #     #     pass
    #     # b = await BigUser._get_(where="name='__dummy__'")
    #     # self.assertEqual(b.age, 23)
    #     pass

    # def clean(self):
    #     SNORM_DB_POOL.close()

    # def test_transaction(self):
    #     try:
    #         asyncio.get_event_loop().run_until_complete(self._test_transaction_setup())
    #         # group = asyncio.gather(self._test_transaction_setup(), *[self._test_transaction() for i in range(10)])
    #         # group = asyncio.gather( *[self._test_transaction() for i in range(10000)])
    #         # group = asyncio.gather(self._test_transaction_setup())
    #         # asyncio.get_event_loop().run_until_complete(asyncio.gather(group))
    #     finally:
    #         self.clean()

    # def _test_something(self):
        # db = DB(SNORM_DB_POOL)
        # dbpool = await db.pool()
        # await dbpool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
        # # await db.execute('INSERT into test_table')
        # mos = await test_table._get_(where='name like $1 order by id asc', prepared_args=['%dumm%'])
        # print(mos.__dict__)
        # # print(mos[0].__dict__)
        # print(BigUser()._fields_)
        # print(BigUser._get_table_name_())
        # b = BigUser()
        # b.name = 'jahid'
        # b.age = 28
        # print(b._get_insert_query_())
        # id = await b._insert_()
        # print(id)

        # b1 = await BigUser._get_(where='id=1')
        # b1.name = 'Jahidul Hamid'
        # print(b1._get_update_query_())
        # await b1._update_()
        # b = BigUser()
        # b.name = 'John Doeee'
        # b.profession = 'Teacher'
        # await b._save_()
        # b.age = 34
        # await b._save_()
        # d = {
        #     'name': 'John Doe',
        #     'age': 45,
        # }
        # b = BigUser(name='Jahid')


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    except:
        SNORM_DB_POOL.close()
        raise
