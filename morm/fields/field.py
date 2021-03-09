"""Field class.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

import copy
from typing import Any, Optional, Callable, Tuple, Dict, List, Union
from morm.types import Void



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
    """This class is easily derivable from a json config.
    """
    def __init__(self, **kwargs):
        """Initialize a sql definition for Field.
        """
        self.conf: Dict[str, str] = kwargs

    def __eq__(self, other: 'ColumnConfig') -> bool:
        return self.conf == other.conf

    def __repr__(self):
        reprs = []
        for k, v in self.conf.items():
            reprs.append(f'{k}={repr(v)}')
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'

    def to_json(self) -> Dict[str, str]:
        return self.conf

    def get_query_column_create_stub(self) -> Tuple[str, str]:
        """Get create query along with alter query for this field

        Can be used to make the create table query.

        Returns:
            Tuple[str, str]: create_query, alter_query
        """
        create_q = f'"{self.conf["column_name"]}" {self.conf["sql_type"]} {self.conf["sql_onadd"]}'
        alter_q, msg = self.get_query_column_settings(())
        return create_q, alter_q


    def get_query_column_add(self) -> Tuple[str, str]:
        """Get a sql query to add the column.

        Returns:
            Tuple[str, str]: sql query, message
        """
        queries = []
        msgs = []
        queries.append(f'ALTER TABLE "{self.conf["table_name"]}" ADD COLUMN "{self.conf["column_name"]}" {self.conf["sql_type"]} {self.conf["sql_onadd"]};')
        msgs.append(f'\n* > ADD: {self.conf["column_name"]}: {self.conf["sql_type"]}')

        q, m = self.get_query_column_settings(())
        if q:
            queries.append(q)
            msgs.append(m)

        if self.conf['sql_engine'] == 'postgresql':
            return '\n'.join(queries), ''.join(msgs)
        else:
            raise ValueError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_drop(self) -> Tuple[str, str]:
        """Get a sql query to drop the column.

        Returns:
            Tuple[str, str]: sql query, message
        """
        query = f'ALTER TABLE "{self.conf["table_name"]}" DROP COLUMN "{self.conf["column_name"]}" {self.conf["sql_ondrop"]};'
        msg = f'\n* > DROP: {self.conf["column_name"]} {self.conf["sql_ondrop"]}'
        if self.conf['sql_engine'] == 'postgresql':
            return query, msg
        else:
            raise ValueError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_rename(self, old_column_name: str) -> Tuple[str, str]:
        """Get a sql query to rename the column.

        Args:
            old_column_name (str)

        Returns:
            Tuple[str, str]: sql query, message
        """
        query = f'ALTER TABLE "{self.conf["table_name"]}" RENAME COLUMN "{old_column_name}" TO "{self.conf["column_name"]}";'
        msg = f"\n* > RENAME: {old_column_name} --> {self.conf['column_name']}"
        if self.conf['sql_engine'] == 'postgresql':
            return query, msg
        else:
            raise ValueError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_modify(self, prev: 'ColumnConfig') -> Tuple[str, str]:
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
            q = f'ALTER TABLE "{self.conf["table_name"]}" ALTER COLUMN "{self.conf["column_name"]}" SET DATA TYPE {self.conf["sql_type"]};'
            queries.append(q)
            msg = f"\n* > MODIFY: {prev.conf['column_name']}: {prev.conf['sql_type']} --> {self.conf['sql_type']}"
            msgs.append(msg)

        settings_query, msg = self.get_query_column_settings(prev.conf['sql_alter'])
        if settings_query:
            queries.append(settings_query)
            msgs.append(msg)


        if self.conf['sql_engine'] == 'postgresql':
            return '\n'.join(queries), ''.join(msgs)
        else:
            raise ValueError(f"{self.conf['sql_engine']} not supported yet.")

    def get_query_column_settings(self, prev_sql_alter: Tuple[str]) -> Tuple[str, str]:
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
            raise TypeError(f"sql_alter {prev_sql_alter} must be a tuple, {type(self.conf['sql_alter'])} given")
        query = ''
        msgs = []
        query_stubs = []
        for qs in self.conf['sql_alter']:
            if qs not in prev_sql_alter:
                # new settings
                query_stubs.append(qs)
                msgs.append(f"\n* + {qs}")
        query_stub = ', '.join([f'ALTER COLUMN "{self.conf["column_name"]}" {x}' for x in query_stubs])
        if query_stub:
            query = f'ALTER TABLE "{self.conf["table_name"]}" {query_stub};'

        if self.conf['sql_engine'] == 'postgresql':
            return query, ''.join(msgs)
        else:
            raise ValueError(f"{self.conf['sql_engine']} not supported yet.")





class Field(object):
    """# Field class.

    Field object stores the sql definition of the model field,
    validator function, modifier function and the default and provides
    some utilities:
    """
    def __init__(self, sql_type: str,
                sql_onadd='',
                sql_ondrop='',
                sql_alter: Tuple[str] = (),
                sql_engine='postgresql',
                default: Any=Void,
                validator: Callable=always_valid,
                modifier: Callable=nomodify,
                fallback=False,):
        """Initialize the Field object with data type (sql).

        Example sql_type: `'varchar(255)'`, `'int'`, etc..

        Example sql_onadd: `'PRIMARY KEY'`, `'NOT NULL'`, `'UNIQUE'`, `'FOREIGHN KEY'` etc..

        Example sql_ondrop: `'CASCADE'` and `'RESTRICT'`

        Example sql_alter settings

        ```sql
        SET DEFAULT expression
        DROP DEFAULT
        { SET | DROP } NOT NULL
        SET STATISTICS integer
        SET ( attribute_option = value [, ... ] )
        RESET ( attribute_option [, ... ] )
        SET STORAGE { PLAIN | EXTERNAL | EXTENDED | MAIN }
        ```

        Args:
            sql_type (str): Data type in SQL.
            sql_onadd (str): sql to add in ADD clause after 'ADD COLUMN column_name data_type'
            sql_ondrop (str): Either 'RESTRICT' or 'CASCADE'.
            sql_alter (Tuple[str]): multiple alter column sql; added after 'ALTER [ COLUMN ] column_name'. Example: ('DROP DEFAULT', 'SET NOT NULL') will alter the default and null settings accordingly.
            sql_engine (str): db engine, postgresql, mysql etc.. Defaults to 'postgresql'
            default (Any, optional): Pythonic default value (can be a callable). Defaults to Void. (Do not use mutable values, use function instead)
            validator (callable, optional): A callable that accepts exactly one argument. Validates the value in `clean` method. Defaults to always_valid.
            modifier (callable, optional): A callable that accepts exactly one argument. Modifies the value if validation fails when the `clean` method is called.. Defaults to nomodify.
            fallback (bool, optional): Whether invalid value should fallback to default value suppressing exception. (May hide bugs in your program)
        """
        self.sql_type = sql_type
        self.sql_conf = ColumnConfig(sql_type=sql_type, sql_onadd=sql_onadd, sql_ondrop=sql_ondrop, sql_alter=sql_alter, sql_engine=sql_engine)
        self.default = default
        self.validator = validator
        self.modifier = modifier
        self._name = ''
        self.fallback = fallback

    def __eq__(self, other: 'Field') -> bool:
        return self.sql_conf == other.sql_conf

    def __repr__(self):
        reprs = [repr(self.sql_type)]
        cc = ['sql_onadd','sql_ondrop','sql_alter','sql_engine',]
        for k in cc:
            reprs.append(f'{k}={repr(self.sql_conf.conf[k])}')
        s = ['default','validator','modifier','fallback',]
        for k in s:
            reprs.append(f'{k}={repr(self.__dict__[k])}')
        body = ', '.join(reprs)
        return f'{self.__class__.__name__}({body})'

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


class FieldValue(object):
    """Field Value Container

    `FieldValue().value` is a property that sets and gets the value.

    `FieldValue().value_change_count` gives the count of how many times the value
    has been set or changed.
    """

    def __init__(self, field: Field):
        """Initialize field Value container.

        Args:
            field (Field): Field object
        """
        self._field = field
        self._value = Void
        self._value_change_count = 0

    @property
    def value_change_count(self) -> int:
        """Return how many times the value has been set or changed.

        Returns:
            Any: value
        """
        return self._value_change_count

    @property
    def value(self) -> Any:
        """Get the value if set or default otherwise.

        Returns:
            Any: value or default
        """
        if self._value is not Void:
            return self._value
        else:
            return self._field.get_default()

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
        self._value_change_count = self._value_change_count + 1 # This must be the last line
        # when the clean method raises exception, it will not be counted as
        # a successful value assignment.

    def delete_value(self):
        """Return the value to its initial state.
        """
        self._value = Void
        # must not change/decrease _value_change_count
        # when this value is set again, the counter should increase
        # according to its previous value.
        # delete itself is a change but it does not change the value
        # to a valid value thus the counter should not increase either.
