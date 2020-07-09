"""Model.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

import typing
from abc import ABCMeta
from morm.exceptions import ItemDoesNotExistError
from morm.fields import Field
from morm.types import Void
from morm.db import DB


class _ModelMeta_(ABCMeta):
    def __new__(mcs, class_name, bases, attrs):
        classcell = attrs.pop('__classcell__', None)
        new_bases = tuple(base._class_ for base in bases if hasattr(base, '_class_'))
        _class_ = super().__new__(mcs, 'x_' + class_name, new_bases, attrs)
        _fields_ = getattr(_class_, '_fields_', {})

        new_attrs = {}
        db_instance_given = False
        for n in dir(_class_):
            v = getattr(_class_, n)
            if isinstance(v, Field):
                if n.startswith('_') and n.endswith('_'):
                    raise AttributeError(f"Invalid field name '{n}' in model '{class_name}'. \
                        Field name must not start and end with an underscore.")
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



class _Model_(metaclass=_ModelMeta_):
    _db_instance_no_check_: bool = True # internal use only

    _db_instance_: typing.Optional[DB] = None
    '''_db_instance_ will be inherited in subclasses'''
    _table_name_: typing.Optional[str] = None
    """_table_name_ will not be inherited in subclasses"""

    _exclude_up_keys_: tuple = ()
    '''Exclude columns for these keys when saving the data to database'''
    _exclude_up_values_: tuple = ()
    '''Exclude columns for these values when saving the data to database'''
    _exclude_down_keys_ : tuple= ()    # TODO: implement in select
    '''Exclude columns for these keys when retrieving data from database'''
    _exclude_down_values: tuple = ()   # TODO: implement in select
    '''Exclude columns for these values when retrieving data from database'''



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
    async def _get_(cls, where='true', prepared_args=None):
        """Get the first item that matches the where condition

        e.g: "name like '%dummy%' and profession='teacher'"

        Args:
            where (str, optional): where condition. Defaults to 'true'.
            prepared_args (list, optional): prepared args. Defaults to None.

        Returns:
            Model: A model instance
        """
        return await cls._select1_(where=where, prepared_args=prepared_args)

    def _active_fields_(self, exclude_values: tuple, exclude_keys: tuple):
        for k,field in self._fields_.items():   # type: ignore
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
            yield k, v, field

    def _get_insert_query_(self, exclude_values=(), exclude_keys=()):
        pk = self._pk_     # type: ignore
        table = self.__class__._get_table_name_()
        query = f"INSERT INTO \"{table}\""
        columns = '('
        values = '('
        args = []
        c = 0
        for k, v, field in self._active_fields_(exclude_values, exclude_keys):
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
        pk = self._pk_     # type: ignore
        try:
            pkval = getattr(self, pk)
            if not pkval:
                raise ItemDoesNotExistError("Can not update. Item does not exist.")
        except AttributeError:
            raise ItemDoesNotExistError("Can not update. Item does not exist.")
        query = f"UPDATE \"{table}\" SET "
        args = []
        c = 0
        for k, v, field in self._active_fields_(exclude_values, exclude_keys):
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

    _db_instance_no_check_: bool = True # internal use only

    _db_instance_: typing.Optional[DB] = None
    '''_db_instance_ will be inherited in subclasses'''
    _table_name_: typing.Optional[str] = None
    """_table_name_ will not be inherited in subclasses"""

    _pk_: str = 'id'
    '''If you use different primary key, you must define it accordingly'''
    id: Field = Field('SERIAL NOT NULL PRIMARY KEY')
    '''Default primary key'''

    def __init__(self, *args, **kwargs):
        for arg in args:
            try:
                for k,v in arg.items():
                    setattr(self, k, v)
            except AttributeError:
                raise ValueError("Invalid argument to Model __init__ method. Expected: dictionary or keyword argument")
        for k,v in kwargs.items():
            setattr(self, k, v)


    def __setattr__(self, k, v):
        if not k.startswith('_') and k not in self._fields_:
            raise AttributeError(f"No such attribute ('{k}') in model '{self.__class__.__name__}''")
        if k in self._fields_:
            v = self._fields_[k].clean(v)
        super().__setattr__(k, v)
