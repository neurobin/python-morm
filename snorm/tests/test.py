import asyncio
import logging
import unittest
from async_property import async_property, async_cached_property

from snorm.db import Pool, DB
from ocd import Void


LOGGER_NAME = 'snorm-'
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
    max_size=100,
)

def always_valid(value):
    return True

def nomodify(value):
    return value

class Field(object):
    def __init__(self, sql_def, default=Void,
                 validator=always_valid,
                 modifier=nomodify):
        self.sql_def = sql_def
        self.default = default
        self.validator = validator
        self.modifier = modifier
        self.name = ''

    def clean(self, value):
        value = self.modifier(value)
        if not self.validator(value):
            raise ValueError("Value did not pass validation check for '%s'" % (self.name,))
        return value

    def get_default(self):
        if callable(self.default):
            return self.default()
        else:
            return self.default

from abc import ABCMeta
from collections import OrderedDict

class ModelMeta(ABCMeta):
    def __new__(mcs, class_name, bases, attrs):
        classcell = attrs.pop('__classcell__', None)
        new_bases = tuple(base._class_ for base in bases if hasattr(base, '_class_'))
        _class_ = super().__new__(mcs, 'x_' + class_name, new_bases, attrs)
        _fields_ = getattr(_class_, '_fields_', {})

        rserved_attrs = ['_class_', '_classcell_', '_fields_',
                        '_select_', '_select1_', '_filter_',
                        '_first_', '_insert_', '_update_',
                        '_save_', '_get_table_name_',
                        '_get_db_instance_',]
        new_attrs = {}

        db_instance_given = False
        for n in dir(_class_):
            v = getattr(_class_, n)
            if isinstance(v, Field):
                if n in rserved_attrs:
                    raise AttributeError("'%s' is a reserved attribute for class"
                                        "'%s' defined in '%r'. Please do not "
                                        "redefine it as a field value." % (n, class_name, mcs,))
                v.name = n
                _fields_[n] = v
            elif n in attrs:
                new_attrs[n] = attrs[n]
            if n == '_db_instance_' and v:
                db_instance_given = True

        new_attrs['_fields_'] = _fields_
        new_attrs['_class_'] = _class_

        if not '_table_name_' in new_attrs:
            new_attrs['_table_name_'] = None
        if not '_db_instance_no_check_' in new_attrs:
            new_attrs['_db_instance_no_check_'] = False
        if not db_instance_given and not new_attrs['_db_instance_no_check_']:
            raise AttributeError(f"Attribute: _db_instance_ must be given in class {class_name}")
        if classcell is not None:
            new_attrs['__classcell__'] = classcell
        return super().__new__(mcs, class_name, bases, new_attrs)

class ItemDoesNotExistError(Exception): pass

class _Model_(metaclass=ModelMeta):
    _db_instance_no_check_ = True # internal use only

    _db_instance_ = None
    '''_db_instance_ will be inherited in subclasses'''
    _table_name_ = None
    """_table_name_ will not be inherited in subclasses"""

    _exclude_up_keys_ = ()
    _exclude_up_values_ = ()
    _exclude_down_keys_ = ()
    _exclude_down_values = ()



    @classmethod
    def _get_table_name_(cls):
        if cls._table_name_:
            return cls._table_name_
        else:
            return cls.__name__

    @classmethod
    def _get_db_instance_(cls):
        return cls._db_instance_

    @classmethod
    async def _select_(cls, what='*', where='true', prepared_args=None):
        """Make a select query for this model.

        Args:
            what (str, optional): Columns. Defaults to '*'.
            where (str, optional): Where conditon (sql). Defaults to 'true'.
            prepared_args (list, optional): prepared arguments. Defaults to None.

        Returns:
            list: List of model instances
        """
        if not prepared_args: prepared_args = []
        query = 'SELECT %s FROM "%s" WHERE %s' % (what, cls._get_table_name_(), where)
        return await cls._get_db_instance_().fetch(query, *prepared_args, model_class=cls)

    @classmethod
    async def _filter_(cls, where='true', prepared_args=None):
        """Filter according to where condition

        e.g: "name like '%dummy%' and profession='teacher'"

        Args:
            where (str, optional): where condition. Defaults to 'true'.
            prepared_args (list, optional): prepared arguments. Defaults to None.

        Returns:
            list: List of model instances.
        """
        return await cls._select_(where=where, prepared_args=prepared_args)

    @classmethod
    async def _select1_(cls, what='*', where='true', prepared_args=None):
        """Make a select query to retrieve one item from this model.

        'LIMIT 1' is added at the end of the query.

        Args:
            what (str, optional): Columns. Defaults to '*'.
            where (str, optional): Where condition. Defaults to 'true'.
            prepared_args (list, optional): prepared arguments. Defaults to None.

        Returns:
            Model: A model instance.
        """
        if not prepared_args: prepared_args = []
        query = 'SELECT %s FROM "%s" WHERE %s LIMIT 1' % (what, cls._get_table_name_(), where)
        return await cls._get_db_instance_().fetchrow(query, *prepared_args, model_class=cls)

    @classmethod
    async def _first_(cls, where='true', prepared_args=None):
        """Get the first item that matches the where condition

        e.g: "name like '%dummy%' and profession='teacher'"

        Args:
            where (str, optional): where condition. Defaults to 'true'.
            prepared_args (list, optional): prepared args. Defaults to None.

        Returns:
            Model: A model instance
        """
        return await cls._select1_(where=where, prepared_args=prepared_args)

    # @classmethod
    # def _get_props_(cls):
    #     props = {}
    #     for k,v in cls._fields_.items():
    #         props[k] = v.sql_def
    #     return props

    def _get_insert_query_(self, exclude_values=(), exclude_keys=()):
        pk = self._pk_
        table = self.__class__._get_table_name_()
        query = f"INSERT INTO \"{table}\""
        columns = '('
        values = '('
        args = []
        c = 0
        for k,field in self._fields_.items():
            if k in exclude_keys \
                or k in self._exclude_up_keys_:
                continue
            v = getattr(self, k, Void)
            if v is Void or v is None:
                v = field.get_default()
            if v is Void:
                # we don't have any value for k
                continue
            if v in exclude_values \
                or v in self._exclude_up_values_:
                continue
            c = c + 1
            columns = f"{columns} \"{k}\","
            values = f"{values} ${c},"
            args.append(v)
        columns = columns.strip(',')
        values = values.strip(',')

        query = f"{query} {columns}) VALUES {values})  RETURNING {pk}"
        return query, args

    def _get_update_query_(self, exclude_values=(), exclude_keys=()):
        table = self.__class__._get_table_name_()
        pk = self._pk_
        try:
            pkval = getattr(self, pk)
            if not pkval:
                raise ItemDoesNotExistError("Can not update. Item does not exist.")
        except AttributeError:
            raise ItemDoesNotExistError("Can not update. Item does not exist.")
        query = f"UPDATE \"{table}\" SET "
        args = []
        c = 0
        for k,field in self._fields_.items():
            if k in exclude_keys \
                or k in self._exclude_up_keys_:
                continue
            v = getattr(self, k, Void)
            if v is Void or v is None:
                v = field.get_default()
            if v is Void:
                # we don't have any value for k
                continue
            if v in exclude_values \
                or v in self._exclude_up_values_:
                continue
            if k == pk:
                continue
            c = c + 1
            query = f"{query} \"{k}\"=${c},"
            args.append(v)
        query = query.strip(',')

        c = c + 1
        query = f"{query} WHERE {pk}=${c}"
        args.append(pkval)

        return query, args

    async def _insert_(self, exclude_values=(), exclude_keys=()):
        query, args = self._get_insert_query_(exclude_values=exclude_values, exclude_keys=exclude_keys)
        cls = self.__class__
        pkval = await cls._get_db_instance_().fetchval(query, *args)
        setattr(self, self._pk_, pkval)
        return pkval

    async def _update_(self, exclude_values=(), exclude_keys=()):
        query, args = self._get_update_query_(exclude_values=exclude_values, exclude_keys=exclude_keys)
        cls = self.__class__
        return await cls._get_db_instance_().fetchrow(query, *args)

    async def _save_(self, exclude_values=(), exclude_keys=()):
        pk = self._pk_
        try:
            return await self._update_(exclude_values=exclude_values, exclude_keys=exclude_keys)
        except ItemDoesNotExistError:
            return await self._insert_(exclude_values=exclude_values, exclude_keys=exclude_keys)



class Model(_Model_):

    _db_instance_no_check_ = True # internal use only

    _db_instance_ = None
    '''_db_instance_ will be inherited in subclasses'''
    _table_name_ = None
    """_table_name_ will not be inherited in subclasses"""

    _pk_ = 'id'
    '''If you use different primary key, you must define it accordingly'''
    id = Field('INT primary key')



class User(Model):
    _db_instance_ = DB(SNORM_DB_POOL)
    name = Field('varchar(255)')
    profession = Field('varchar(255)')

class BigUser(User):
    age = Field("int")


class test_table(User):pass



class TestMethods(unittest.TestCase):

    async def _test_default(self):
        db = DB(SNORM_DB_POOL)
        dbpool = await db.pool()
        await dbpool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
        # await db.execute('INSERT into test_table')
        mos = await test_table._first_(where='name like $1 order by id asc', prepared_args=['%dumm%'])
        print(mos.__dict__)
        # # print(mos[0].__dict__)
        # print(BigUser()._fields_)
        # print(BigUser._get_table_name_())
        # b = BigUser()
        # b.name = 'jahid'
        # b.age = 28
        # print(b._get_insert_query_())
        # id = await b._insert_()
        # print(id)

        # b1 = await BigUser._first_(where='id=1')
        # b1.name = 'Jahidul Hamid'
        # print(b1._get_update_query_())
        # await b1._update_()
        b = BigUser()
        b.name = 'John Doe'
        b.profession = 'Teacher'
        await b._save_()
        b.age = 32
        await b._save_()

    def test_default(self):
        asyncio.get_event_loop().run_until_complete(self._test_default())

if __name__ == "__main__":
    unittest.main()
