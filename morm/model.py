"""Model.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

import inspect
import typing
from typing import Optional, Dict, List, Tuple, TypeVar, Union, Any, Iterator
from collections import OrderedDict
import copy
from abc import ABCMeta
from asyncpg import Record # type: ignore
from morm.exceptions import ItemDoesNotExistError
from morm.fields.field import Field, FieldValue
from morm.types import Void
import morm.meta as mt      # for internal use

# morm.db must not be imported here.

Meta = mt.Meta  # For client use


class _FieldNames():
    """Access field names
    """
    def __init__(self, func):
        self.__dict__['func'] = func

    def __getattr__(self, k):
        return self.__dict__['func'](k)

    def __setattr__(self, k, v):
        raise NotImplementedError


class ModelType(type):
    Meta: typing.ClassVar # fixing mypy error: "ModelType" has no attribute "Meta"
    def __new__(mcs, class_name: str, bases: tuple, attrs: dict):
        # Ensure initialization is only performed for subclasses of Model
        # excluding Model class itself.
        parents = tuple(b for b in bases if isinstance(b, ModelType))
        if not parents:
            return super().__new__(mcs, class_name, bases, attrs)

        classcell = attrs.pop('__classcell__', None)
        class _Meta_(mt.Meta): pass
        meta = attrs.pop('Meta', _Meta_)
        if not inspect.isclass(meta): #TEST: Meta is restricted as a class
            raise TypeError(f"Name 'Meta' is reserved for a class to pass configuration or metadata of a model. Error in model '{class_name}'")
        _class_ = super().__new__(mcs, 'x_' + class_name, parents, attrs)
        BaseMeta = getattr(_class_, 'Meta', _Meta_)

        meta_attrs = {}
        def _set_meta_attr(k, v, mutable=False, inherit=True, internal=False):
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
                # mutable values can be changed by other class meta change
                if mutable:
                    meta_attrs[k] = copy.deepcopy(v)
                else:
                    meta_attrs[k] = v

        _set_meta_attr('proxy', False)
        _set_meta_attr('pk', 'id')
        _set_meta_attr('ordering', ())
        _set_meta_attr('fields_up', ())
        _set_meta_attr('fields_down', ())
        _set_meta_attr('exclude_fields_up', ())
        _set_meta_attr('exclude_fields_down', ())
        _set_meta_attr('exclude_values_up', {'':()}, mutable=True)
        _set_meta_attr('exclude_values_down', {'':()}, mutable=True)
        _set_meta_attr('_field_defs_', {}, internal=True, mutable=True)

        if meta_attrs['proxy']:
            #proxy model inherits everything
            try:
                meta_attrs['db_table'] = BaseMeta.db_table
                meta_attrs['abstract'] = BaseMeta.abstract
            except AttributeError:
                raise TypeError(f"This model '{class_name}' can not be a proxy model. It does not have a valid base or super base non-proxy model")
        else:
            _set_meta_attr('abstract', False, inherit=False)
            if meta_attrs['abstract']:
                meta_attrs['db_table'] = Void
            else:
                _set_meta_attr('db_table', class_name, inherit=False)

        new_attrs = {}

        # dict is ordered, officially from python 3.7
        for n, v in _class_.__dict__.items():
            if isinstance(v, Field):
                if n.startswith('_'):
                    raise AttributeError(f"Invalid field name '{n}' in model '{class_name}'. \
                        Field name must not start with underscore.")
                if meta_attrs['proxy'] and n in attrs:
                    raise ValueError(f"Proxy model '{class_name}' can not define new field: {n}")
                v.name = n
                # v.sql_conf.conf['table_name'] = meta_attrs['db_table'] # Field must not contain table_name, because it is void when model is abstract and it gets inherited.
                meta_attrs['_field_defs_'][n] = v
            elif n in attrs:
                new_attrs[n] = attrs[n]

        # we do this after finalizing meta_attr
        def _get_field_name(n: str) -> str:
            if n in meta_attrs['_field_defs_']:
                return n
            else:
                raise AttributeError(f"No such field '{n}' in model '{class_name}'")
        meta_attrs['f'] = _FieldNames(_get_field_name)

        MetaClass = mt.MetaType('Meta', (mt.Meta,), meta_attrs)
        new_attrs['Meta'] = MetaClass

        if classcell is not None:
            new_attrs['__classcell__'] = classcell
        return super().__new__(mcs, class_name, bases, new_attrs)

    def __setattr__(self, k, v):
        raise NotImplementedError("You can not set model attributes outside model definition.")

    def __delattr__(self, k):
        raise NotImplementedError("You can not delete model attributes outside model definition.")

    def _is_valid_key_(self, k:str, fields:Tuple[str], exclude_keys:Tuple[str]) -> bool:
        """Returns True if the key is valid considering include/exclude keys
        """
        if k in exclude_keys: return False
        if fields and k not in fields: return False
        return True

    def _is_valid_down_key_(self, k: str) -> bool:
        """Returns True if the key is valid considering include/exclude down keys
        """
        return self._is_valid_key_(k, self.Meta.fields_down, self.Meta.exclude_fields_down)

    def _is_valid_up_key_(self, k: str) -> bool:
        """Returns True if the key is valid considering include/exclude up keys
        """
        return self._is_valid_key_(k, self.Meta.fields_up, self.Meta.exclude_fields_up)

    def _is_valid_value_(self, k: str, v: Any, exclude_values: Dict[str, Tuple[Any]]) -> bool:
        """Returns True if the value for the key is valid considering exclude values
        """
        if v is Void:
            return False
        if k in exclude_values:
            if v in exclude_values[k]:
                return False
        if '' in exclude_values and v in exclude_values['']:
            return False
        return True

    def _is_valid_up_value_(self, k: str, v: Any) -> bool:
        """Returns True if the value for the key is valid considering exclude up values
        """
        return self._is_valid_value_(k, v, self.Meta.exclude_values_up)

    def _is_valid_down_value_(self, k: str, v: Any) -> bool:
        """Returns True if the value for the key is valid considering exclude down values
        """
        return self._is_valid_value_(k, v, self.Meta.exclude_values_down)

    def _is_valid_down_(self, k: str, v: Any) -> bool:
        """Check whether the key and value is valid for down (data retrieval)
        """
        return self._is_valid_down_key_(k) and self._is_valid_down_value_(k, v)

    def _is_valid_up_(self, k: str, v: Any) -> bool:
        """Check whether the key and value is valid for up (data update)
        """
        return self._is_valid_up_key_(k) and self._is_valid_up_value_(k, v)

    def _get_all_fields_(self) -> Dict[str, Field]:
        """Get all fields on model without applying any restriction.

        Returns:
            Dict[str, Field]: Dictionary of all fields
        """
        return self.Meta._field_defs_

    def _check_field_name_(self, n: str) -> str:
        """Return the field name if exists else raise AttributeError

        Args:
            n (str): field name

        Raises:
            AttributeError: if field name does not exist

        Returns:
            str: field name
        """
        if n in self.Meta._field_defs_:
            return n
        else:
            raise AttributeError(f"No such field `{n}` in model `{self.__name__}`")

    def _get_fields_(self, up=False) -> Iterator[str]:
        """Yields field names that pass include/exclude criteria

        Args:
            up (bool, optional): up criteria or down criteria. Defaults to False (down).

        Yields:
            str: field name
        """
        if up:
            fields = self.Meta.fields_up
            exclude_keys = self.Meta.exclude_fields_up
        else:
            fields = self.Meta.fields_down
            exclude_keys = self.Meta.exclude_fields_down
        all_fields = self._get_all_fields_()
        for k in all_fields:
            if not self._is_valid_key_(k, fields, exclude_keys):
                continue
            yield k

    def _get_FieldValue_data_valid_(self, data: dict, up=False) -> Iterator[Tuple[str, Any]]:
        """Yields valid key,value pairs from data.

        Validity is checked against include/exclude key/value criteria.

        Args:
            data (dict): data to be validated.
            up (bool, optional): whether up (data update) or down (data retrieval). Defaults to False.

        Yields:
            Iterator[Tuple[str, Any]]: Yields key, value pair
        """
        if up:
            exclude_values = self.Meta.exclude_values_up
            fields = self.Meta.fields_up
            exclude_fields = self.Meta.exclude_fields_up
        else:
            exclude_values = self.Meta.exclude_values_down
            fields = self.Meta.fields_down
            exclude_fields = self.Meta.exclude_fields_down
        # new_data = type(data)()
        for k,v in data.items():
            if not self._is_valid_key_(k, fields, exclude_fields):
                continue
            if not self._is_valid_value_(k, v.value, exclude_values):
                continue
            yield k, v


    # def _get_data_for_valid_values_(self, data, up=False, gen=False):
    #     if up:
    #         exclude_values = self.Meta.exclude_values_up
    #     else:
    #         exclude_values = self.Meta.exclude_values_down
    #     new_data = type(data)()
    #     for k,v in data.items():
    #         if not self._is_valid_value_(k, v, exclude_values):
    #             continue
    #         if gen:
    #             yield k, v
    #         else:
    #             new_data[k] = v
    #     if not gen:
    #         return new_data

    def _get_db_table_(self) -> str:
        """Get db table name for model
        """
        return self.Meta.db_table

    def _is_abstract_(self) -> bool:
        """Whether it's an abstract model or not
        """
        return self.Meta.abstract

    def _is_proxy_(self) -> bool:
        """Whether it is a proxy model or not
        """
        return self.Meta.proxy

    def _get_pk_(self) -> str:
        """Get primary column name
        """
        return self.Meta.pk

    def _get_ordering_(self, quote: str) -> Iterator[Tuple[str, str]]:
        """Yield each ordering from model parsed and converted to column, direction

        direction is either `ASC` or `DESC`

        Args:
            quote (str): Quote to apply to the column

        Yields:
            Iterator[Tuple[str, str]]: Yields column, direction
        """
        ordering = self.Meta.ordering
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
    """Base Model for all models.

    Do not inherit from this class, use Model instead.

    Raises:
        TypeError: When invalid type is encountered
        AttributeError: When misspelled fields are tried to set.
    """
    class Meta:
        """Meta that holds metadata for model
        """
        # The following needs to be defined here, not in meta.Meta
        # meta.Meta is used in client Models, thus everything
        # included there will be blindly inherited, while these are passed
        # through the metaclasses __new__ methods and processed accordingly
        # to determine which one should be inherited and which one should not.
        pk = 'id'
        '''Primary key'''
        db_table = Void
        abstract = True
        proxy = False
        ordering = ()
        fields_up = ()
        fields_down = ()
        exclude_fields_up = ()
        exclude_fields_down = ()
        exclude_values_up = {'':()}
        exclude_values_down = {'':()}

        #internal
        _field_defs_: Dict[str, Field]
        _fields_: Dict[str, FieldValue]
        _fromdb_: List[str]


    def __init__(self, *args, **kwargs):
        class Meta:
            _fields_: Dict[str, FieldValue] = {}
            _fromdb_: List[str] = []
        # super(ModelBase, self).__setattr__('Meta', Meta)
        self.__dict__['Meta'] = Meta
        for k, v in self.__class__.Meta._field_defs_.items():
            self.Meta._fields_[k] = FieldValue(v)
        for arg in args:
            try:
                arg_items = arg.items()
            except AttributeError:
                raise TypeError(f"Invalid argument type ({type(arg)}) to Model __init__ method. Expected: dictionary or keyword argument")
            for k,v in arg_items:
                setattr(self, k, v)
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
        Meta = self.__dict__['Meta']
        fields = Meta._fields_
        if k in fields:
            v = fields[k].value
            if self.__class__._is_valid_down_(k, v):
                return v
            raise AttributeError(f'Invalid attempt to access field `{k}`. It is excluded using either exclude_fields_down or exclude_values_down in {self.__class__.__name__} Meta class. Or it does not have any valid value.')
        raise AttributeError

    def __setattr__(self, k: str, v):
        if k == 'Meta':
            raise AttributeError(f"Name '{k} is reserved. You should not try to change it.")
        if k.startswith('_'):
            if k.endswith('_'):
                raise AttributeError('_<name>_ such names are reserved for predefined methods.')
            self.__dict__[k] = v
            return
        fields = self.Meta._fields_
        if k not in fields:
            raise AttributeError(f"No such field ('{k}') in model '{self.__class__.__name__}''")
        # v = fields[k].clean(v)
        # super().__setattr__(k, v)
        if self.__class__._is_valid_up_(k, v):
            if k in self.Meta._fromdb_:
                fields[k]._ignore_first_change_count_ = True
                self.Meta._fromdb_.remove(k)
            fields[k].value = v
        elif k in self.Meta._fromdb_:
            self.Meta._fromdb_.remove(k)
        else:
            raise AttributeError(f'Can not set field `{k}`. It is excluded using either exclude_fields_up or exclude_values_up in {self.__class__.__name__} Meta class. Or you are trying to set an invalid value: {v}')

    def __repr__(self):
        reprs = []
        for k, v in self:
            reprs.append(f'{k}={repr(v)}')
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'


    async def _pre_save_(self, db):
        """Pre-save hook.

        Override to run pre save cleanup.

        Args:
            db (DB): db handle.
        """
        pass

    async def _pre_delete_(self, db):
        """Pre-delete hook.

        Override to run pre delete cleanup.

        Args:
            db (DB): db handle.
        """
        pass


    async def _post_save_(self, db):
        """Pre-save hook.

        Override to run post save cleanup.

        Args:
            db (DB): db handle.
        """
        pass

    async def _post_delete_(self, db):
        """Pre-delete hook.

        Override to run post delete cleanup.

        Args:
            db (DB): db handle.
        """
        pass



    async def _pre_insert_(self, db):
        """Pre-insert hook.

        Override to run pre insert cleanup.

        Args:
            db (DB): db handle.
        """
        pass

    async def _pre_update_(self, db):
        """Pre-update hook.

        Override to run pre update cleanup.

        Args:
            db (DB): db handle.
        """
        pass


    async def _post_insert_(self, db):
        """Pre-insert hook.

        Override to run post insert cleanup.

        Args:
            db (DB): db handle.
        """
        pass

    async def _post_update_(self, db):
        """Pre-update hook.

        Override to run post update cleanup.

        Args:
            db (DB): db handle.
        """
        pass



class Model(ModelBase):
    """Base model to be inherited by other models.

    It's more than a good practice to define a Base model first:

    ```python
    from morm.model import Model
    from morm.datetime import timestamp

    class Base(Model):
        class Meta:
            pk = 'id' # setting primary key, it is defaulted to 'id'
            abstract = True

        # postgresql example
        id = Field('SERIAL', sql_onadd='PRIMARY KEY NOT NULL')
        created_at = Field('TIMESTAMP WITH TIME ZONE', sql_onadd='NOT NULL', sql_alter=('ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT NOW()',))
        updated_at = Field('TIMESTAMP WITH TIME ZONE', sql_onadd='NOT NULL', value=timestamp)
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
            # see morm.meta.Meta for supported meta attributes.

        name = Field('varchar(65)')
        email = Field('varchar(255)')
        password = Field('varchar(255)')
        profession = Field('varchar(255)', default='Unknown')
        random = Field('integer', default=get_rand) # function can be default
    ```

    ## Initialize a model instance

    keyword arguments initialize corresponding fields according to
    the keys.

    Positional arguments must be dictionaries of
    keys and values.

    Example:

    ```python
    User(name='John Doe', profession='Teacher')
    User({'name': 'John Doe', 'profession': 'Teacher'})
    User({'name': 'John Doe', 'profession': 'Teacher'}, age=34)
    User({'name': 'John Doe', 'profession': 'Teacher', 'active': True}, age=34)
    ```

    Raises:
        TypeError: If invalid type of argument is provided.

    ## Special Model Meta attribute `f`:

    You can access field names from `ModelClass.Meta.f`.

    This allows a spell-safe way to write the field names. If you
    misspell the name, you will get `AttributeError`.

    ```python
    f = User.Meta.f
    my_data = {
        f.name: 'John Doe',         # safe from spelling mistake
        f.profession: 'Teacher',    # safe from spelling mistake
        'hobby': 'Gardenning',      # unsafe from spelling mistake
    }
    ```
    """
    class Meta:
        # The following needs to be defined here, not in meta.Meta
        # meta.Meta is used in client Models, thus everything
        # included there will be blindly inherited, while these are passed
        # through the metaclasses __new__ methods and processed accordingly
        # to determine which one should be inherited and which one should not.
        abstract = True

    def __init__(self, *args, **kwargs):
        super(Model, self).__init__(*args, **kwargs)
