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
import morm.fields.field as fdl


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

from morm.model import Model
from morm.fields import Field

def mprint(*args, **kwargs):
    print("-"*80)
    print(*args, **kwargs)
    print("-"*80)

class TestMethods(unittest.TestCase):

    def checkModelAttributeSet(self, name, value):
        print(f"> set attribute '{name}' for model class must produce NotImplementedError")
        with self.assertRaises(NotImplementedError):
            class User(Model):pass
            setattr(User, name, value)


    def checkModelAttributeDel(self, name):
        print(f"> del attribute '{name}' for model class must produce NotImplementedError")
        with self.assertRaises(NotImplementedError):
            class User(Model):pass
            delattr(User, name)

    def checkMetaAttributeSet(self, name, value):
        print(f"> set attribute '{name}' for Meta class of model must produce NotImplementedError")
        with self.assertRaises(NotImplementedError):
            class User(Model):
                class Meta(mdl.Meta): pass
                setattr(Meta, name, value)

    def checkMetaAttributeDel(self, name, value):
        print(f"> del attribute '{name}' for Meta class of model must produce NotImplementedError")
        with self.assertRaises(NotImplementedError):
            class User(Model):
                class Meta(mdl.Meta): pass
                delattr(Meta, name)

    def test_Model_Attr_Set_Del(self):
        attrs = ['Meta', 'name', 'dummy', 'hozoborolo']
        for k in attrs:
            self.checkModelAttributeSet(k, 32)
            self.checkModelAttributeDel(k)

    def test_Model_Meta(self):
        print("> Meta can not be anything other than a class")
        with self.assertRaises(TypeError):
            class User(Model):
                Meta = 32

    def test_Model_Meta_Internal_fields(self):
        print("> _field_defs_ internal meta field can not be set by user.")
        with self.assertRaises(ValueError):
            class User(Model):
                class Meta(mdl.Meta):
                    _field_defs_ = 67576

    def test_Model_Meta_Attr_Set_Del(self):

        meta_attrs = {
            'pk': 23,
            'proxy': 23,
            'ordering': 23,
            'fields_up': 23,
            'fields_down': 23,
            'exclude_fields_up': 23,
            'exclude_fields_down': 23,
            'exclude_values_up': 23,
            'exclude_values_down': 23,
            'db_table': 23,
            'abstract': 23,
        }

        for k, v in meta_attrs.items():
            self.checkMetaAttributeSet(k, v)
            self.checkMetaAttributeDel(k, v)

    def checkMetaAttributeType(self, name, value):
        print(f"> set attribute '{name}' with invalid (typed) value {value} for Meta class in Model must produce TypeError")
        with self.assertRaises(TypeError):
            class User(Model):
                Meta = mt.MetaType('Meta', (mt.Meta,), {name: value})

    def test_Model_Meta_Attr_Types(self):

        meta_attrs = {
            'pk': 23,
            'proxy': 23,
            'ordering': 23,
            'fields_up': 23,
            'fields_down': 23,
            'exclude_fields_up': 23,
            'exclude_fields_down': 23,
            'exclude_values_up': 23,
            'exclude_values_down': 23,
            'db_table': 23,
            'abstract': 23,
        }

        for k, v in meta_attrs.items():
            self.checkMetaAttributeType(k, v)

    def test_Model_Meta_Attr_Defaults(self):
        class User(Model):
            profession = Field('varchar(255)')
            name = Field('varchar(255)')
        class BigUser(User):
            age = Field("int")

        print("> db_table default value must be the class name")
        self.assertEqual(User.Meta.db_table, 'User')
        self.assertEqual(BigUser.Meta.db_table, 'BigUser')

        print("> Meta._field_defs_ must be a dict")
        self.assertTrue(isinstance(User.Meta._field_defs_, dict))

        meta_attrs_defaults = {
            'pk': 'id',
            'abstract': False,
            'proxy': False,
            'ordering': (),
            'fields_up': (),
            'fields_down': (),
            'exclude_fields_up': (),
            'exclude_fields_down': (),
            'exclude_values_up': {'':()},
            'exclude_values_down': {'':()},
        }
        for k, v in meta_attrs_defaults.items():
            gv = getattr(BigUser.Meta, k)
            print(f"> User Model without Meta class must have default value {v} for Meta attribute {k}")
            self.assertEqual(gv, v)




    def test_Model_Meta_Attribute_Definition(self):
        class User(Model):
            class Meta:
                pk = 'column_id'
                db_table = 'myapp_model_user'
                abstract = True
                proxy = False
                ordering = ('id', 'name')
                fields_up = ('id', 'name')
                fields_down = ('id', 'name')
                exclude_fields_up = ('updated_at',)
                exclude_fields_down = ('password',)
                exclude_values_up = {'': ('', None)}
                exclude_values_down = {'':('', None)}

        meta_attr_inh = {
            'pk': 'column_id',
            'proxy': False,
            'ordering': ('id', 'name'),
            'fields_up': ('id', 'name'),
            'fields_down': ('id', 'name'),
            'exclude_fields_up': ('updated_at',),
            'exclude_fields_down': ('password',),
            'exclude_values_up': {'': ('', None)},
            'exclude_values_down': {'': ('', None)},
        }

        meta_attrs_no_inh = {
            'db_table': Void,
            'abstract': True,
        }

        meta_attrs = {**meta_attr_inh, **meta_attrs_no_inh}

        for k, v in meta_attrs.items():
            print(f"> Meta attribute value for '{k}' must match with defined custom value: {v}")
            self.assertEqual(getattr(User.Meta, k), v)

        # checking Meta inheritance
        class User2(User):
            class Meta:
                pk = 'column_id'
                proxy = False
                ordering = ('id', 'name')
                fields_up = ('id', 'name')
                fields_down = ('id', 'name')
                exclude_fields_up = ('updated_at',)
                exclude_fields_down = ('password',)
                exclude_values_up = {'': ('', None)}
                exclude_values_down = {'': ('', None)}

        class User3(User): pass


        for k, v in meta_attr_inh.items():
            print(f"> Meta attribute value for '{k}' must match with inherited value: {v}")
            self.assertEqual(getattr(User3.Meta, k), v)


        meta_attrs_no_inh_default = {
            'db_table': 'User3',
            'abstract': False,
        }
        for k, v in meta_attrs_no_inh.items():
            mv = getattr(User3.Meta, k)
            dv = meta_attrs_no_inh_default[k]
            print(f"> Meta attribute value for '{k}' must not be inherited and match the default value: {dv}")
            self.assertEqual(mv, dv)

        ############################
        # check proxy
        ############################

        meta_attr_inh = {
            'pk': 'column_id',
            'proxy': True,
            'ordering': ('id', 'name'),
            'fields_up': ('id', 'name'),
            'fields_down': ('id', 'name'),
            'exclude_fields_up': ('updated_at',),
            'exclude_fields_down': ('password',),
            'exclude_values_up': {'': ('', None)},
            'exclude_values_down': {'': ('', None)},
        }

        meta_attrs_no_inh = {
            'db_table': Void,
            'abstract': True,
        }

        meta_attrs = {**meta_attr_inh, **meta_attrs_no_inh}

        # checking Meta inheritance
        class User2(User):
            class Meta:
                proxy = True

        # class User3(User): pass
        print(' - [x] db_table must be the same for proxy models')
        self.assertEqual(User2.Meta.db_table, User.Meta.db_table)

        for k, v in meta_attr_inh.items():
            print(f"> Proxy:True: Meta attribute value for '{k}' must match with inherited value: {v}")
            self.assertEqual(getattr(User2.Meta, k), v)

        meta_attrs_no_inh_default = {
            'db_table': Void,
            'abstract': True,
        }
        for k, v in meta_attrs_no_inh.items():
            mv = getattr(User2.Meta, k)
            print(f"> Proxy:True: Meta attribute value for '{k}' must be inherited and match the value: {v}")
            self.assertEqual(mv, v)

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
        print("> set attribute on model instance for non-existence field must produce AttributeError")
        with self.assertRaises(AttributeError):
            user.profesion = 'Teacher' # spelling mistake

        print("> del attribute on model instance is allowed")
        del user.profession
        # mprint(inspect.getsource(BigUser2))
        # mprint(user)

    def test_Model_Proxy(self):
        class User(Model):
            name = Field('varchar(255)')
            profession = Field('varchar(255)')
            age = Field("int")
        print("> Proxy model can not include new fields")
        with self.assertRaises(ValueError):
            class Me(User):
                fdslkjlds = Field('varchar(255)')
                name = 34
                class Meta(mdl.Meta):
                    proxy = True

    def test_Model_Field_Order(self):
        class User(Model):
            name = Field('varchar(255)')
            profession = Field('varchar(255)')
            age = Field("int")

        keys = ['name', 'profession', 'age']
        ckey = list(User.Meta._field_defs_.keys())
        print("> Class attribute definition order must be preserved (requires python 3.7+)")
        self.assertEqual(keys, ckey)

    def test_Model_Field(self):
        def name_default():
            return random.choice(User.NAMES)

        class User(Model):
            NAMES = ['John Doe', 'Jane Doe']
            name = Field('varchar(255)', default=name_default)
            profession = Field('varchar(255)', default='Teacher')
            age = Field("int")

        user = User()
        self.assertTrue(user.name in User.NAMES)
        user.name = 'Jahidul Hamid'
        self.assertEqual('Jahidul Hamid', user.name)
        print("> Field().name represents the string name of the field")
        self.assertTrue(User.Meta._field_defs_['name'].name == 'name')

        print("> Model instance is iterable (k,v)")
        for k, v in user:
            print((k, v,))

        with self.assertRaises(AttributeError):
            class User2(Model):
                NAMES = ['John Doe', 'Jane Doe']
                __name__ = Field('varchar(255)', default=name_default)

    def test_Model_Init(self):

        class User(Model):
            NAMES = ['John Doe', 'Jane Doe']
            name = Field('varchar(255)', default='John Doe')
            profession = Field('varchar(255)', default='Teacher')
            age = Field("int", default=23)
            hobby = Field('varchar(255)', default='Gardenning')
            status = Field('varchar(255)', default='NOK')
            marital_status = Field('varchar(255)', default='Single')
            address = Field('varchar(255)', default='Gardenning Park')
            class Meta:
                fields_up = ('name', 'profession', 'age', 'status', 'marital_status', 'address')
                exclude_fields_up = ('profession',)
                exclude_values_up = {
                    '': ('Single',),
                    'address': ('Gardenning Park',),
                }
                fields_down = ('name', 'profession', 'age', 'hobby', 'status', 'marital_status', 'address')
                exclude_fields_down = ('age',)
                exclude_values_down = {
                    '': ('NOK',),
                    'address': (None,),
                }

        user = User({'name': 'Student'}, name='Jahid')
        with self.assertRaises(TypeError):
            user = User(['name', 'Student'], name='Jahid')
        with self.assertRaises(AttributeError):
            dct = user.fdsfdss
        del user.__dict__ # for coverage to touch __delattr__

        # value = fdl.FieldValue(Field('varchar(255)', default='something'))
        # nokvalue = fdl.FieldValue(Field('varchar(255)', default='something'))
        # nokvalue.value = 'NOK'
        # singlevalue = fdl.FieldValue(Field('varchar(255)', default='something'))
        # singlevalue.value = 'Single'
        # print('\n#'*10)
        # print(value.value)
        user = User()
        data = user.Meta._fields_

        ans = [
            ('name', data['name']),
            ('profession', data['profession']),
            ('hobby', data['hobby']),
            ('marital_status', data['marital_status']),
            ('address', data['address']),
        ]
        c = 0
        for k, v in User._get_FieldValue_data_valid_(data, up=False):
            self.assertIn((k, v), ans)
            c += 1
        self.assertEqual(c, len(ans))

        ans = [
            ('name', data['name']),
            ('age', data['age']),
            ('status', data['status']),
        ]
        c = 0
        for k, v in User._get_FieldValue_data_valid_(data, up=True):
            self.assertIn((k, v), ans)
            c += 1
        self.assertEqual(c, len(ans))

        ans = ['name', 'profession', 'hobby', 'status', 'marital_status', 'address']
        c = 0
        for k in User._get_fields_():
            self.assertIn(k, ans)
            c += 1
        self.assertEqual(c, len(ans))

        ans = ['name', 'age', 'status', 'marital_status', 'address']
        c = 0
        for k in User._get_fields_(up=True):
            self.assertIn(k, ans)
            c += 1
        self.assertEqual(c, len(ans))



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
        # mos = await test_table._get_(where='name like $1 order by id asc', args=['%dumm%'])
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
        # SNORM_DB_POOL.close()
        raise
