"""Field class.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

import copy, inspect
from typing import Any, Optional, Callable, Tuple, Dict, List, Union
from morm.types import Void
import morm.exceptions as ex


def always_valid(value: Any)-> bool:
    """Always return True regradless of the value.

    Args:
        value (Any): value to be validated.

    Returns:
        bool: True
    """
    return True

def nomodify(value: Any) -> Any:
    """Return the value without any modification.

    Args:
        value (Any): Any value.

    Returns:
        Any: The save value that is passed.
    """
    return value


class ColumnConfig():
    """Config container for each column/feild.

    This class is easily derivable from a json config.
    """
    def __init__(self, **kwargs):
        self.conf: Dict[str, Union[str, Tuple[str, ...]]] = kwargs

    def __eq__(self, other: 'ColumnConfig') -> bool: # type: ignore
        return self.conf['sql_alter'] == other.conf['sql_alter']\
                and self.conf['sql_type'] == other.conf['sql_type']\
                and self.conf['sql_ondrop'] == other.conf['sql_ondrop']

    def __repr__(self):
        reprs = []
        for k, v in self.conf.items():
            reprs.append(f'{k}={repr(v)}')
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'

    def to_json(self) -> Dict[str, Union[str, Tuple[str, ...]]]:
        return self.conf

    def get_query_column_create_stub(self, table_name: str) -> Tuple[str, str]:
        """Get create query along with alter query for this field

        Can be used to make the create table query.

        Returns:
            Tuple[str, str]: create_query, alter_query
        """
        create_q = f'"{self.conf["column_name"]}" {self.conf["sql_type"]} {self.conf["sql_onadd"]}'
        alter_q, msg = self.get_query_column_alter((), table_name)
        return create_q, alter_q


    def get_query_column_add(self, table_name: str) -> Tuple[str, str]:
        """Get a sql query to add the column.

        Returns:
            Tuple[str, str]: sql query, message
        """
        queries = []
        msgs = []
        queries.append(f'ALTER TABLE "{table_name}" ADD COLUMN "{self.conf["column_name"]}" {self.conf["sql_type"]} {self.conf["sql_onadd"]};')
        msgs.append(f'\n* > ADD: {self.conf["column_name"]}: {self.conf["sql_type"]}')

        q, m = self.get_query_column_alter((), table_name)
        if q:
            queries.append(q)
            msgs.append(m)

        if self.conf['sql_engine'] == 'postgresql':
            return '\n'.join(queries), ''.join(msgs)
        else:
            raise ex.UnsupportedError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_drop(self, table_name: str) -> Tuple[str, str]:
        """Get a sql query to drop the column.

        Returns:
            Tuple[str, str]: sql query, message
        """
        query = f'ALTER TABLE "{table_name}" DROP COLUMN "{self.conf["column_name"]}" {self.conf["sql_ondrop"]};'
        msg = f'\n* > DROP: {self.conf["column_name"]} {self.conf["sql_ondrop"]}'
        if self.conf['sql_engine'] == 'postgresql':
            return query, msg
        else:
            raise ex.UnsupportedError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_rename(self, old_column_name: str, table_name: str) -> Tuple[str, str]:
        """Get a sql query to rename the column.

        Args:
            old_column_name (str)

        Returns:
            Tuple[str, str]: sql query, message
        """
        query = f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_column_name}" TO "{self.conf["column_name"]}";'
        msg = f"\n* > RENAME: {old_column_name} --> {self.conf['column_name']}"
        if self.conf['sql_engine'] == 'postgresql':
            return query, msg
        else:
            raise ex.UnsupportedError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_modify(self, prev: 'ColumnConfig', table_name: str) -> Tuple[str, str]:
        """Get a sql query to modify data type of the column.

        Args:
            prev (ColumnConfig): previous column config

        Returns:
            Tuple[str, str]: sql query, message
        """
        # TODO: handle alter settings.
        queries = []
        msgs = []
        if self.conf['sql_type'] != prev.conf['sql_type']:
            q = f'ALTER TABLE "{table_name}" ALTER COLUMN "{self.conf["column_name"]}" SET DATA TYPE {self.conf["sql_type"]};'
            queries.append(q)
            msg = f"\n* > MODIFY: {prev.conf['column_name']}: {prev.conf['sql_type']} --> {self.conf['sql_type']}"
            msgs.append(msg)

        settings_query, msg = self.get_query_column_alter(prev.conf['sql_alter'], table_name) # type: ignore
        if settings_query:
            queries.append(settings_query)
            msgs.append(msg)


        if self.conf['sql_engine'] == 'postgresql':
            return '\n'.join(queries), ''.join(msgs)
        else:
            raise ex.UnsupportedError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_alter(self, prev_sql_alter: Tuple[str, ...], table_name: str) -> Tuple[str, str]:
        """Get a sql query to apply the sql_alter settings comparing with
        another config: prev.

        Args:
            prev_sql_alter (Tuple[str]): previous sql_alter

        Returns:
            Tuple[str, str]: sql query, message
        """
        if not isinstance(prev_sql_alter, (tuple, list,)):
            raise TypeError(f"sql_alter {prev_sql_alter} must be a tuple, {type(prev_sql_alter)} given")
        if not isinstance(self.conf['sql_alter'], (tuple, list,)):
            raise TypeError(f"sql_alter {self.conf['sql_alter']} must be a tuple, {type(self.conf['sql_alter'])} given")
        query = ''
        msgs = []
        query_stubs = []
        column_name = self.conf["column_name"]
        for qs in self.conf['sql_alter']:
            if qs not in prev_sql_alter:
                # new settings
                qs = qs.format(table=table_name, column=column_name)
                query_stubs.append(qs)
                msgs.append(f"\n* + {qs}")

        if query_stubs:
            query = '; '.join(query_stubs) + ';'

        if self.conf['sql_engine'] == 'postgresql':
            return query, ''.join(msgs)
        else:
            raise ex.UnsupportedError(f"{self.conf['sql_engine']} not supported yet.")


def is_sql_array(value: Any) -> bool:
    """Check if the value is a list of sql values.

    Args:
        value (list): list of values

    Returns:
        bool: True if the value is a list of sql values
    """
    if not isinstance(value, list): return False
    if len(value) == 0: return True
    t = type(value[0])
    for v in value:
        if type(v) != t:
            return False
    return True


def sql_val(value: Any, sql_type: str) -> str:
    """Return the value as a string that can be used in sql.

    Args:
        value (Any): Any value

    Returns:
        str: string representation of the value
    """
    if isinstance(value, list):
        return f"ARRAY[{', '.join([str(sql_val(x, sql_type)) for x in value])}]" if value else f'ARRAY[]::{sql_type}'
    value = str(value)
    if value.lower() in ['true']: return 'true'
    if value.lower() in ['false']: return 'false'
    if value.lower() in ['null','none']: return 'null'
    try:
        if '.' in value: return float(value)
        return int(value)
    except:
        return f"'{value}'"


class Field(object):
    """Initialize the Field object with data type (sql).

    Example sql_type: `'varchar(255)'`, `'integer'`, etc..

    Example sql_onadd: `'PRIMARY KEY'`, `'NOT NULL'`, `'UNIQUE'` etc..
    `sql_onadd` is only for adding the column, thus a change to this
    parameter will not trigger any change for the field.

    Example sql_ondrop: `'CASCADE'` and `'RESTRICT'`

    Example sql_alter queries

    ```sql
    ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT expression
    ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT
    ALTER TABLE "{table}" ALTER COLUMN "{column}" SET NOT NULL
    ALTER TABLE "{table}" ALTER COLUMN "{column}" SET STATISTICS integer
    ALTER TABLE "{table}" ALTER COLUMN "{column}" SET ( attribute_option = value [, ... ] )
    ALTER TABLE "{table}" ALTER COLUMN "{column}" RESET ( attribute_option [, ... ] )
    ALTER TABLE "{table}" ALTER COLUMN "{column}" SET STORAGE { PLAIN | EXTERNAL | EXTENDED | MAIN }
    ```

    {table} and {column} will be replaced with table name,
    and column name respectively.


    Args:
        sql_type (str): Data type in SQL.
        sql_onadd (str): sql to add in ADD clause after 'ADD COLUMN column_name data_type'
        sql_ondrop (str): Either 'RESTRICT' or 'CASCADE'.
        sql_alter (Tuple[str]): Alter column queries; Example: ('ALTER TABLE "{table}" ALTER COLUMN "{column}" DROP DEFAULT',).
        sql_engine (str): db engine, postgresql, mysql etc.. Defaults to 'postgresql'
        default (Any, optional): Pythonic default value (can be a callable). Defaults to Void. (Do not use mutable values, use function instead)
        value (Any, optional): Set a value that will prevail unless changed manually. Can be a function. Useful to make updated_at like fields.
        choices (Tuple[Tuple[str, Any], ...], optional): choices tuple: (('Name of choice', 'value'), ...)
        help_text (str, optional):  help text to describe this field.
        validator (callable, optional): A callable that accepts exactly one argument. Validates the value in `clean` method. Defaults to always_valid.
        modifier (callable, optional): A callable that accepts exactly one argument. Modifies the value if validation fails when the `clean` method is called.. Defaults to nomodify.
        fallback (bool, optional): Whether invalid value should fallback to default value suppressing exception. (May hide bugs in your program)
    """
    def __init__(self, sql_type: str,
                sql_onadd='',
                sql_ondrop='',
                sql_alter: Tuple[str, ...] = (),
                sql_engine='postgresql',
                default: Any=Void,
                value: Any=Void,
                unique=False,
                choices: Tuple[Tuple[str, Any], ...] = (),
                help_text: str = '',
                validator: Callable=always_valid,
                modifier: Callable=nomodify,
                fallback=False,): # if you add new param here, update __repr__ method
        # Rules for using a variable name here as local variables go into the self._json_:
        # 1. Must precede with underscore if not in the parameter list
        # 2. Make sure to exclude unnecessary variables in the self._json_ like 'self' etc..
        _init_args = list(locals().keys())[1:] # this must be the first line here in __init__

        self.sql_type = sql_type
        _unique_constraint = '__UNQ_{table}_{column}__'
        if unique:
            _sql_unique = 'ALTER TABLE "{table}" ADD CONSTRAINT "%s" UNIQUE ("{column}");' % (_unique_constraint,)
        else:
            _sql_unique = 'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "%s";' % (_unique_constraint,)
        sql_alter = (_sql_unique, *sql_alter)
        # handle default
        if isinstance(default, (int, float, str, bool)) or is_sql_array(default):
            sql_alter = (*sql_alter, "ALTER TABLE \"{table}\" ALTER COLUMN \"{column}\" SET DEFAULT "+f"{sql_val(default, sql_type)};")
        self.sql_conf = ColumnConfig(sql_type=sql_type, sql_onadd=sql_onadd, sql_ondrop=sql_ondrop, sql_alter=sql_alter, sql_engine=sql_engine)
        self.validator = validator
        self.modifier = modifier
        self._name = ''
        self.fallback = fallback
        self._is_perpetual_default = False
        if value is not Void:
            self.default = value
            self._is_perpetual_default = True
            if default is not Void:
                raise ValueError(f"Parameter 'value' and 'default' both can not be set at the same time.")
        else:
            self.default = default
        self.choices = choices
        self.help_text = help_text

        # make a json
        self._json_ = {
            '_name': self.name,
            '_init_args': _init_args,
        }
        args = locals()
        for k,v in args.items():
            if k in ['self', '_init_args']: continue
            if callable(v):
                self._json_[k] = inspect.getsource(v)
            else:
                self._json_[k] = 'Void' if v == Void else v


    def __eq__(self, other: 'Field') -> bool: # type: ignore
        return other and self.sql_conf == other.sql_conf

    def __repr__(self):
        reprs = []
        for k in self._json_['_init_args']:
            if k == 'sql_type': reprs.append(repr(self.sql_type))
            elif k in ['sql_onadd','sql_ondrop','sql_alter','sql_engine',]:
                reprs.append(f'{k}={repr(self.sql_conf.conf[k])}')
            else:
                try:
                    if callable(self.__dict__[k]):
                        reprs.append(f'{k}={inspect.getsource(self.__dict__[k])}')
                    else:
                        reprs.append(f'{k}={repr(self.__dict__[k])}')
                except KeyError: pass
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'

    def to_json(self):
        res = self._json_.copy()
        res['_name'] = self.name
        res['_repr'] = self.__repr__()
        del res['_init_args']
        return res

    def __invert__(self):
        return self.name

    @property
    def name(self) -> str:
        """Get the name of the field"""
        return self._name

    @name.setter
    def name(self, v: str):
        """Set the name of the field"""
        self._name = v
        self.sql_conf.conf['column_name'] = v

    def clean(self, value: Any, fallback: bool=False):
        """Clean the value by calling validator -> modifier -> validator

        If fallback is set to True, value that does not pass the
        validator will not raise any exception and will return the
        default value.


        Args:
            value (Any): Any value
            fallback (bool, optional): Fallback to default. Defaults to False.

        Raises:
            ValueError: If validation fails

        Returns:
            Any: value
        """
        if not self.validator(value):
            value = self.modifier(value)
        else:
            return value
        # the value may have been changed, try to validate again
        if not self.validator(value):
            if fallback:
                return self.get_default()
            raise ValueError("Value (%s) (type: %s) did not pass validation check for '%s'" % (str(value), type(value), self.name,))
        return value

    def get_default(self):
        """Get the default value.

        The default given is treated as a callable first, if it fails
        then it is returned as a value.

        Returns:
            Any: default value
        """
        try:
            return self.default()
        except TypeError:
            return self.default


class FieldValue():
    """Field Value Container

    `FieldValue().value` is a property that sets and gets the value.

    `FieldValue().value_change_count` gives the count of how many times the value
    has been set or changed.

    Args:
        field (Field): Field object
    """

    def __init__(self, field: Field):
        self._field = field
        self._value = Void
        self.value_change_count = 0
        self._ignore_first_change_count_ = False

    def __eq__(self, other):
        return self._field == other._field and self._value == other._value

    @property
    def value_change_count(self) -> int:
        """Return how many times the value has been set or changed.

        Returns:
            Any: value
        """
        return self.__value_change_count

    @value_change_count.setter
    def value_change_count(self, v: Any):
        """Set value change counter

        Args:
            v (Any): value
        """
        if not self._field._is_perpetual_default:
            self.__value_change_count = v
        else:
            self.__value_change_count = 1 # always change

    @property
    def value(self) -> Any:
        """Get the value if set or default otherwise.

        Returns:
            Any: value or default
        """
        if self._value is Void or (self._field._is_perpetual_default and self.value_change_count == 0):
            return self._field.get_default()
        return self._value

    @value.setter
    def value(self, v: Any):
        """Set the value by doing cleanup.

        Falls back to default if value is invalid.

        Args:
            v (Any): value
        """
        self.set_value(v, fallback=self._field.fallback)

    def set_value(self, v: Any, fallback=False):
        """Value setter.

        Args:
            v (Any): value
            fallback (bool, optional): Whether to fallback to default value if v is invalid. Defaults to False.
        """
        self._value = self._field.clean(v, fallback=fallback)
        if not self._ignore_first_change_count_: # if from db, then value change count won't change
            self.value_change_count += 1 # This must be the last line
        self._ignore_first_change_count_ = False
        # when the clean method raises exception, it will not be counted as
        # a successful value assignment.

    def delete_value(self):
        """Return the value to its initial state.
        """
        self._value = Void
        # must not change/decrease value_change_count
        # when this value is set again, the counter should increase
        # according to its previous value.
        # delete itself is a change but it does not change the value
        # to a valid value thus the counter should not increase either.
