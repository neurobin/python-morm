"""Model.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

import inspect
import typing
from collections import OrderedDict
import copy
from abc import ABCMeta
from asyncpg import Record # type: ignore
from morm.exceptions import ItemDoesNotExistError
from morm.fields.field import Field, FieldValue
from morm.types import Void, imdict
import morm.meta as mt      # for internal use

# morm.db must not be imported here.

Meta = mt.Meta  # For client use


class ModelType(type):
    def __new__(mcs, class_name: str, bases: tuple, attrs: dict):
        # Ensure initialization is only performed for subclasses of Model
        # excluding Model class itself.
        parents = tuple(b for b in bases if isinstance(b, ModelType))
        if not parents:
            return super().__new__(mcs, class_name, bases, attrs)

        classcell = attrs.pop('__classcell__', None)
        class _Meta_(): pass
        meta = attrs.pop('Meta', _Meta_)
        if not inspect.isclass(meta): #TEST: Meta is restricted as a class
            raise TypeError(f"Name 'Meta' is reserved for a class to pass configuration or metadata of a model. Error in model '{class_name}'")
        _class_ = super().__new__(mcs, 'x_' + class_name, parents, attrs)
        BaseMeta = getattr(_class_, 'Meta', _Meta_)

        # parse and update meta
        meta_attrs_inheritable = {
            'pk': 'id',
            'proxy': False,             # TODO: Implement in migration
            'ordering': (),
            'fields_up': (),
            'fields_down': (),
            'exclude_fields_up': (),
            'exclude_fields_down': (),
            'exclude_values_up': {'':()},
            'exclude_values_down': {'':()},
        }
        meta_attrs_noninheritable = {
            'db_table': class_name,
            'abstract': False,          # TODO: Implement in migration
        }

        meta_attrs_inheritable_internal = { # type: ignore
            # for preserving order, python 3.6+ is required.
            # This library requires at least 3.7
            '_field_defs_': {},         # Internal, Dicts are ordered from python 3.6, officially from 3.7
        }

        meta_attrs = {}
        def set_meta_attrs(meta, meta_attrs_current, inherit=False, internal=False):
            for k, v in meta_attrs_current.items():
                try:
                    given_value = getattr(meta, k)
                    if internal:
                        raise ValueError(f"'{k}' is a reserved attribute for class Meta. Error in model '{class_name}'")
                    given_type = type(given_value)
                    required_type = type(v)
                    if not given_type is required_type:
                        raise TypeError(f"Invalid type {given_type} given for attribute '{k}' in class '{class_name}.Meta'. Required {required_type}.")
                    meta_attrs[k] = given_value
                except AttributeError:
                    if inherit:
                        v = getattr(BaseMeta, k, v)
                        # here deepcopy fixes a bug
                        # mutable values can be changed by other class meta change
                        meta_attrs[k] = copy.deepcopy(v)
                    else:
                        meta_attrs[k] = v
        set_meta_attrs(meta, meta_attrs_inheritable, inherit=True)
        set_meta_attrs(meta, meta_attrs_noninheritable, inherit=False)
        set_meta_attrs(meta, meta_attrs_inheritable_internal, inherit=True, internal=True)


        new_attrs = {}

        # https://www.python.org/dev/peps/pep-0520
        # PEP 520 says: dir() will not depend on __definition_order__
        # Even though as of python 3.8.3 we see dir() also preserves order
        # but let's be safe.
        # for n in dir(_class_):
        #     v = getattr(_class_, n)
        for n, v in _class_.__dict__.items():
            if isinstance(v, Field):
                if n.startswith('__') and n.endswith('__'):
                    raise AttributeError(f"Invalid field name '{n}' in model '{class_name}'. \
                        Field name must not start and end with double underscore.")
                if meta_attrs['proxy'] and n in attrs:
                    raise ValueError(f"Proxy model '{class_name}' can not define new field: {n}")
                v.name = n
                meta_attrs['_field_defs_'][n] = v
            elif n in attrs:
                new_attrs[n] = attrs[n]

        MetaClass = mt.MetaType('Meta', (mt.Meta,), meta_attrs)
        new_attrs['Meta'] = MetaClass

        if classcell is not None:
            new_attrs['__classcell__'] = classcell
        return super().__new__(mcs, class_name, bases, new_attrs)

    def __setattr__(cls, k, v):
        raise NotImplementedError("You can not set model attributes outside model definition.")

    def __delattr__(cls, k):
        raise NotImplementedError("You can not delete model attributes outside model definition.")

    def _is_valid_key_(cls, k, fields, exclude_keys):
        if k in exclude_keys: return False
        if fields and k not in fields: return False
        return True

    def _is_valid_down_key_(cls, k):
        return cls._is_valid_key_(k, cls.Meta.fields_down, cls.Meta.exclude_fields_down)

    def _is_valid_up_key_(cls, k):
        return cls._is_valid_key_(k, cls.Meta.fields_up, cls.Meta.exclude_fields_up)

    def _is_valid_value_(cls, k, v, exclude_values):
        if v is Void:
            return False
        if k in exclude_values:
            if v in exclude_values[k]:
                return False
        if '' in exclude_values and v in exclude_values['']:
            return False
        return True

    def _is_valid_up_value_(cls, k, v):
        return cls._is_valid_value_(k, v, cls.Meta.exclude_values_up)

    def _is_valid_down_value_(cls, k, v):
        return cls._is_valid_value_(k, v, cls.Meta.exclude_values_down)

    def _is_valid_down_(cls, k, v):
        return cls._is_valid_down_key_(k) and cls._is_valid_down_value_(k, v)

    def _is_valid_up_(cls, k, v):
        return cls._is_valid_up_key_(k) and cls._is_valid_up_value_(k, v)

    def _get_all_fields_(cls):
        return cls.Meta._field_defs_

    def _get_field_name_(cls, n):
        try:
            return cls.Meta._field_defs_[n].name
        except KeyError:
            raise AttributeError(f"No such field `{n}` in model `{cls.__name__}`")

    def _get_fields_(cls, up=False):
        """Generator

        [extended_summary]

        Args:
            up (bool, optional): [description]. Defaults to False.

        Yields:
            [type]: [description]
        """
        if up:
            fields = cls.Meta.fields_up
            exclude_keys = cls.Meta.exclude_fields_up
        else:
            fields = cls.Meta.fields_down
            exclude_keys = cls.Meta.exclude_fields_down
        all_fields = cls._get_all_fields_()
        for k in all_fields:
            if not cls._is_valid_key_(k, fields, exclude_keys):
                continue
            yield k

    def _get_FieldValue_data_valid_(cls, data, up=False):
        if up:
            exclude_values = cls.Meta.exclude_values_up
            fields = cls.Meta.fields_up
            exclude_fields = cls.Meta.exclude_fields_up
        else:
            exclude_values = cls.Meta.exclude_values_down
            fields = cls.Meta.fields_down
            exclude_fields = cls.Meta.exclude_fields_down
        # new_data = type(data)()
        for k,v in data.items():
            if not cls._is_valid_key_(k, fields, exclude_fields):
                continue
            if not cls._is_valid_value_(k, v.value, exclude_values):
                continue
            yield k, v


    def _get_data_for_valid_values_(cls, data, up=False, gen=False):
        if up:
            exclude_values = cls.Meta.exclude_values_up
        else:
            exclude_values = cls.Meta.exclude_values_down
        new_data = type(data)()
        for k,v in data.items():
            if not cls._is_valid_value_(k, v, exclude_values):
                continue
            if gen:
                yield k, v
            else:
                new_data[k] = v
        if not gen:
            return new_data

    def _get_db_table_(cls):
        return cls.Meta.db_table

    def _is_abstract_(cls):
        return cls.Meta.abstract

    def _is_proxy_(cls):
        return cls.Meta.proxy

    def _get_pk_(cls):
        return cls.Meta.pk

    def _get_ordering_(cls, quote='"'):
        ordering = cls.Meta.ordering
        direction = 'ASC'
        for o in ordering:
            if o.startswith('-'):
                direction = 'DESC'
                o = o[1:]
            elif o.startswith('+'):
                o = o[1:]
            o = f"{quote}{o}{quote}"
            yield o, direction








class ModelBase(metaclass=ModelType):
    """Base Model without any default fields.

    Use Model instead, if you are not an advanced user.

    Meta.pk is set to 'id', you must specify a new primary key and change
    it accordingly if you use this model as your base model.

    Raises:
        TypeError: When invalid typeis encountered
        AttributeError: When misspelled fields are tried to set.
    """
    class Meta(mt.Meta):
        # The following needs to be defined here, not in meta.Meta
        # meta.Meta is used in client Models, thus everything
        # included there will be blindly inherited, while these are passed
        # through the metaclasses __new__ methods and processed accordingly
        # to determine which one should be inherited and which one should not.
        pk = 'id'
        db_table = ''
        abstract = True
        proxy = False
        ordering = ()
        fields_up = ()
        fields_down = ()
        exclude_fields_up = ()
        exclude_fields_down = ()
        exclude_values_up = {'':()}
        exclude_values_down = {'':()}


    def __init__(self, *args, **kwargs):
        class Meta(object): pass
        super(ModelBase, self).__setattr__('Meta', Meta)
        self.Meta._fromdb_ = []
        self.Meta._fields_ = {}
        for k, v in self.__class__.Meta._field_defs_.items():
            self.Meta._fields_[k] = FieldValue(v)
        for arg in args:
            try:
                for k,v in arg.items():
                    setattr(self, k, v)
            except AttributeError:
                raise TypeError(f"Invalid argument type ({type(arg)}) to Model __init__ method. Expected: dictionary or keyword argument")
        for k,v in kwargs.items():
            setattr(self, k, v)

    def __iter__(self):
        """Iter through k, v where k is field name and v is field value

        Yields:
            tuple: field_name, field_value
        """
        for k, f in self.Meta._fields_.items():
            if self.__class__._is_valid_down_(k, f.value):
                yield k, f.value

    def __delattr__(self, k):
        fields = self.Meta._fields_
        if k in fields:
            fields[k].delete_value()
        else:
            super().__delattr__(k)

    def __getattr__(self, k):
        fields = self.Meta._fields_
        if k in fields:
            v = fields[k].value
            if self.__class__._is_valid_down_(k, v):
                return v
            raise AttributeError(f'Invalid attempt to access field `{k}`. It is excluded using either exclude_fields_down or exclude_values_down in {self.__class__.__name__} Meta class')
        raise AttributeError

    def __setattr__(self, k, v):
        fields = self.Meta._fields_
        if k not in fields:
            raise AttributeError(f"No such field ('{k}') in model '{self.__class__.__name__}''")
        # v = fields[k].clean(v)
        # super().__setattr__(k, v)
        if self.__class__._is_valid_up_(k, v):
            fields[k].value = v
        else:
            raise AttributeError(f'Can not set field `{k}`. It is excluded using either exclude_fields_up or exclude_values_up in {self.__class__.__name__} Meta class ')

    def __repr__(self):
        reprs = []
        for k, v in self:
            reprs.append(f'{k}={repr(v)}')
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'



class Model(ModelBase):
    """Base model to be inherited by other models.

    It's more than a good practice to define a Base model first:

    ```python
    import morm.model as mdl

    class Base(mdl.Model):
        class Meta:
            pk = 'id' # setting primary key, it is defaulted to 'id'
            abstract = True

        id = Field('SERIAL NOT NULL PRIMARY KEY') #postgresql example
    ```

    Then a minimal model could look like this:

    ```python
    class User(Base):
        name = Field('varchar(65)')
        email = Field('varchar(255)')
        password = Field('varchar(255)')
    ```

    An advanced model could look like:

    ```python
    import random

    def get_rand():
        return random.randint(1, 9)

    class User(Base):
        class Meta:
            db_table = 'myapp_user'
            abstract = False    # default is False
            proxy = False       # default is False
            # ... etc...

        name = Field('varchar(65)')
        email = Field('varchar(255)')
        password = Field('varchar(255)')
        profession = Field('varchar(255)', default='Unknown')
        random = Field('int', default=get_rand) # function can be default
    ```
    """
    class Meta(mt.Meta):
        # The following needs to be defined here, not in meta.Meta
        # meta.Meta is used in client Models, thus everything
        # included there will be blindly inherited, while these are passed
        # through the metaclasses __new__ methods and processed accordingly
        # to determine which one should be inherited and which one should not.
        abstract = True

    def __init__(self, *args, **kwargs):
        """# Initialize a model instance.

        keyword arguments initialize corresponding fields according to
        the keys.

        Positional arguments must be dictionaries of
        keys and values.

        Example:

        ```
        Model(name='John Doe', profession='Teacher')
        Model({'name': 'John Doe', 'profession': 'Teacher'})
        Model({'name': 'John Doe', 'profession': 'Teacher'}, age=34)
        Model({'name': 'John Doe', 'profession': 'Teacher', 'active': True}, age=34)
        ```

        Raises:
            TypeError: If invalid type of argument is provided.
        """
        super(Model, self).__init__(*args, **kwargs)

# class _Model_(metaclass=ModelType):
#     _db_no_check_: bool = True # internal use only

#     _db_: typing.Any = None
#     '''_db_ will be inherited in subclasses'''
#     _table_name_: typing.Optional[str] = None
#     """_table_name_ will not be inherited in subclasses"""

#     _exclude_fields_up_: tuple = ()
#     '''Exclude columns for these keys when saving the data to database'''
#     _exclude_values_up_: tuple = ()
#     '''Exclude columns for these values when saving the data to database'''
#     _exclude_fields_down_ : tuple= ()    # TODO: implement in select
#     '''Exclude columns for these keys when retrieving data from database'''
#     _exclude_values_down: tuple = ()   # TODO: implement in select
#     '''Exclude columns for these values when retrieving data from database'''


#     @classmethod
#     def _get_table_name_(cls):
#         if cls._table_name_:
#             return cls._table_name_
#         else:
#             return cls.__name__

#     @classmethod
#     async def _select_(cls, what='*', where='true', prepared_args=(), con=None):
#         """Make a select query for this model.

#         Args:
#             what (str, optional): Columns. Defaults to '*'.
#             where (str, optional): Where conditon (sql). Defaults to 'true'.
#             prepared_args (tuple, optional): prepared arguments. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.

#         Returns:
#             list: List of model instances
#         """
#         query = 'SELECT %s FROM "%s" WHERE %s' % (what, cls._get_table_name_(), where)
#         return await cls._db_.fetch(query, *prepared_args, model_class=cls, con=con)

#     @classmethod
#     async def _filter_(cls, where='true', prepared_args=(), con=None):
#         """Filter according to where condition

#         e.g: "name like '%dummy%' and profession='teacher'"

#         Args:
#             where (str, optional): where condition. Defaults to 'true'.
#             prepared_args (tuple, optional): prepared arguments. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.

#         Returns:
#             list: List of model instances.
#         """
#         return await cls._select_(where=where, prepared_args=prepared_args, con=con)

#     @classmethod
#     async def _select1_(cls, what='*', where='true', prepared_args=(), con=None):
#         """Make a select query to retrieve one item from this model.

#         'LIMIT 1' is added at the end of the query.

#         Args:
#             what (str, optional): Columns. Defaults to '*'.
#             where (str, optional): Where condition. Defaults to 'true'.
#             prepared_args (tuple, optional): prepared arguments. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.

#         Returns:
#             Model: A model instance.
#         """
#         query = 'SELECT %s FROM "%s" WHERE %s LIMIT 1' % (what, cls._get_table_name_(), where)
#         return await cls._db_.fetchrow(query, *prepared_args, model_class=cls, con=con)

#     @classmethod
#     async def _get_(cls, where='true', prepared_args=(), con=None):
#         """Get the first item that matches the where condition

#         e.g: "name like '%dummy%' and profession='teacher'"

#         Args:
#             where (str, optional): where condition. Defaults to 'true'.
#             prepared_args (tuple, optional): prepared args. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.

#         Returns:
#             Model: A model instance
#         """
#         return await cls._select1_(where=where, prepared_args=prepared_args, con=con)

#     @classmethod
#     async def _update_(cls, what: str = '',
#                         where: str = '',
#                         prepared_args=(),
#                         returning_column=0,
#                         con=None):
#         """Make an update query.

#         Args:
#             what (str, optional): what query, e.g "name='John Doe'". Defaults to ''.
#             where (str, optional): where query, e.g "id=2". Defaults to ''.
#             prepared_args (tuple, optional): Defaults to ().
#             returning_column (int, optional): index of column from the result to return. Defaults to 0.
#             con (asyncpg.Connection, optional): Connection object. Defaults to None.

#         Raises:
#             ValueError: If what or where query is not given

#         Returns:
#             Any: value of the index 'column' from the query result.
#         """
#         if not what or not where:
#             raise ValueError("what or where value missing.")
#         query = 'UPDATE "%s" SET %s WHERE %s' % (cls._get_table_name_(), what, where)
#         return await cls._db_.fetchval(query, *prepared_args, column=returning_column, con=con) # type: ignore



#     def _active_fields_(self, exclude_values: tuple, exclude_keys: tuple):
#         for k,field in self._fields_.items():   # type: ignore
#             if k in exclude_keys \
#                 or k in self._exclude_fields_up_:
#                 continue
#             v = getattr(self, k, Void)
#             if v is Void or v is None:
#                 v = field.get_default()
#             if v is Void:
#                 # we don't have any value for k
#                 continue
#             if v in exclude_values \
#                 or v in self._exclude_values_up_:
#                 continue
#             yield k, v, field

#     def _get_insert_query_(self, exclude_values=(), exclude_keys=()):
#         pk = self._pk_     # type: ignore
#         table = self.__class__._get_table_name_()
#         query = f"INSERT INTO \"{table}\""
#         columns = '('
#         values = '('
#         args = []
#         c = 0
#         for k, v, field in self._active_fields_(exclude_values, exclude_keys):
#             c = c + 1
#             columns = f"{columns} \"{k}\","
#             values = f"{values} ${c},"
#             args.append(v)
#         columns = columns.strip(',')
#         values = values.strip(',')

#         query = f"{query} {columns}) VALUES {values})  RETURNING {pk}"
#         return query, args

#     def _get_update_query_(self, exclude_values=(), exclude_keys=()):
#         table = self.__class__._get_table_name_()
#         pk = self._pk_     # type: ignore
#         try:
#             pkval = getattr(self, pk)
#             if not pkval:
#                 raise ItemDoesNotExistError("Can not update. Item does not exist.")
#         except AttributeError:
#             raise ItemDoesNotExistError("Can not update. Item does not exist.")
#         query = f"UPDATE \"{table}\" SET "
#         args = []
#         c = 0
#         for k, v, field in self._active_fields_(exclude_values, exclude_keys):
#             c = c + 1
#             query = f"{query} \"{k}\"=${c},"
#             args.append(v)
#         query = query.strip(',')

#         c = c + 1
#         query = f"{query} WHERE {pk}=${c}"
#         args.append(pkval)

#         return query, args

#     async def _insert_me_(self, exclude_values=(), exclude_keys=(), con=None):
#         """Attempt an insert with the data on this model instance.

#         Args:
#             exclude_values (tuple, optional): Exclude columns that matches one of these values. Defaults to ().
#             exclude_keys (tuple, optional): Exclude columns that matches one of these keys. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.
#         """
#         query, args = self._get_insert_query_(exclude_values=exclude_values, exclude_keys=exclude_keys)
#         cls = self.__class__
#         pkval = await cls._db_.fetchval(query, *args, column=0, con=con)
#         setattr(self, self._pk_, pkval)

#     async def _update_me_(self, exclude_values=(), exclude_keys=(), con=None):
#         """Attempt an update with the data on this model instance.

#         Args:
#             exclude_values (tuple, optional): Exclude columns that matches one of these values. Defaults to ().
#             exclude_keys (tuple, optional): Exclude columns that matches one of these keys. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.
#         """
#         query, args = self._get_update_query_(exclude_values=exclude_values, exclude_keys=exclude_keys)
#         cls = self.__class__
#         await cls._db_.fetchrow(query, *args, model_class=cls, con=con)

#     async def _save_(self, exclude_values=(), exclude_keys=(), con=None):
#         """Attempt to save the data on this model instance.

#         If pk exists, the data is updated and if pk does not exist,
#         the data is inserted.

#         Args:
#             exclude_values (tuple, optional): Exclude columns that matches one of these values. Defaults to ().
#             exclude_keys (tuple, optional): Exclude columns that matches one of these keys. Defaults to ().
#             con (asyncpg.Connection, optional): Defaults to None.
#         """
#         try:
#             await self._update_me_(exclude_values=exclude_values, exclude_keys=exclude_keys, con=con)
#         except ItemDoesNotExistError:
#             await self._insert_me_(exclude_values=exclude_values, exclude_keys=exclude_keys, con=con)



# class Model(_Model_):
#     """Base model class that must be inherited to make a model.

#     example model classes would look like:

#     ```python
#     from morm import Model, Field
#     from morm.db import DB, Pool

#     class Base(Model):
#         _db_ = DB(MORM_DB_POOL)
#         # we generally will not create any table for this model.

#     class User(Base):
#         _table_name_ = 'User' # if not given, class name will be table name.

#         name = Field('varchar(100)')
#         email = Field('varchar(256)')
#         password = Field('varchar(256)')
#     ```

#     `MORM_DB_POOL` is a `Pool` object with database settings. Example:

#     ```python
#     MORM_DB_POOL = Pool(
#         dsn='postgres://',
#         host='localhost',
#         port=5432,
#         user='jahid',
#         password='jahid',
#         database='test',
#         min_size=10,
#         max_size=100,
#     )
#     ```

#     The default primary key is `id`. If you want to set a custom primary
#     key, you must define `_pk_` accordingly (`_pk_ = 'id'` by default)

#     You must not use any custom name that starts with a single underscore and
#     ends with a single underscore. This naming convention is reserved by
#     Model class intself and all predefined variable names and method names
#     follow this rule.

#     For field names, do not start with an underscore. This way, you will
#     be protected from spelling mistakes. For example, if you have defined
#     a field named `name` and then try to do

#     ```python
#     user.namee = 'John Doe' # throws AttributeError
#     ```

#     you will get an Attribute error.

#     # Handling data

#     ## Save/Update/Insert

#     ```python
#     user = User(name='John Doe', email='jd@ex.com')
#     user._save_() # saves the data in db (update if exists, otherwise insert)
#     ```

#     ## Select/Filter/Get

#     ### Select

#     ```python
#     users = User._select_(what='*', where="name like '%Doe%'")
#     # users is a list of User object
#     ```

#     ### Select one item (first item)

#     ```python
#     # LIMIT 1 is added to the where quey, do not add it explicitly
#     user = User._select1_(what='*', where="name like '%Doe%' order by name asc")
#     # user is a User object
#     ```

#     ### Filter

#     ```python
#     users = User._filter_(where="name like '%Doe%'")
#     # users is a list of User object
#     ```

#     ### Get

#     ```python
#     # LIMIT 1 is added to the where quey, do not add it explicitly
#     user = User._get_(where='id=3')
#     # user is a User object
#     ```

#     **where query accepts prepared statement**. All of the above methods
#     can take a keyword argument `prepared_args` which is a list (or tuple) of
#     prepared arguments. Example:

#     ```python
#     # LIMIT 1 is added to the where quey, do not add it explicitly
#     user = User._get_(where='id=$1', prepared_args=[3])
#     # user is a User object
#     ```

#     """

#     _db_no_check_: bool = True # internal use only

#     _db_: typing.Any = None
#     '''_db_ will be inherited in subclasses'''

#     _table_name_: typing.Optional[str] = None
#     """_table_name_ will not be inherited in subclasses"""

#     _pk_: str = 'id'
#     '''If you use different primary key, you must define it accordingly'''

#     id = Field('SERIAL NOT NULL PRIMARY KEY')
#     '''Default primary key'''

#     def __init__(self, *args, **kwargs):
#         """# Initialize a model instance.

#         keyword arguments initialize corresponding fields according to
#         the keys.

#         Positional arguments must be dictionaries of
#         keys and values.

#         Example:

#         ```
#         Model(name='John Doe', profession='Teacher')
#         Model({'name': 'John Doe', 'profession': 'Teacher'})
#         Model({'name': 'John Doe', 'profession': 'Teacher'}, age=34)
#         Model({'name': 'John Doe', 'profession': 'Teacher', 'active': True}, age=34)
#         ```

#         Raises:
#             TypeError: If invalid type of argument is provided.
#         """
#         for arg in args:
#             try:
#                 for k,v in arg.items():
#                     setattr(self, k, v)
#             except AttributeError:
#                 raise TypeError("Invalid argument type to Model __init__ method. Expected: dictionary or keyword argument")
#         for k,v in kwargs.items():
#             setattr(self, k, v)


#     def __setattr__(self, k, v):
#         if not k.startswith('_') and k not in self._fields_:
#             raise AttributeError(f"No such attribute ('{k}') in model '{self.__class__.__name__}''")
#         if k in self._fields_:
#             v = self._fields_[k].clean(v)
#         super().__setattr__(k, v)
