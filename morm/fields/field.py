"""Field class.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

from typing import Any, Optional, Callable
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


class Field(object):
    """# Field class.

    Field object stores the sql definition of the model field,
    validator function, modifier function and the default and provides
    some utilities:

    `Field().clean(value, fallback=False)` provides a cleaning method.

    `Field().get_default()` gives you the default value.
    """
    def __init__(self, sql_def: str, default: Any=Void,
                 validator: Callable=always_valid,
                 modifier: Callable=nomodify,
                 fallback=False):
        """Initialize the Field object.

        Args:
            sql_def (str): SQL definition of the model Field
            default (Any, optional): Default value (can be a callable). Defaults to Void. (Do not use mutable values, use function instead)
            validator (callable, optional): A callable that accepts exactly one argument. Validates the value in `clean` method. Defaults to always_valid.
            modifier (callable, optional): A callable that accepts exactly one argument. Modifies the value if validation fails when the `clean` method is called.. Defaults to nomodify.
            fallback (bool, optional): Whether invalid value should fallback to default value suppressing exception. (May hide bugs in your program)
        """
        self.sql_def = sql_def
        self.default = default
        self.validator = validator
        self.modifier = modifier
        self.name = ''
        self.fallback = fallback

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
        self._had_previous_value = False

    @property
    def had_previous_value(self):
        return self._had_previous_value

    @property
    def value_change_count(self):
        """Return how many times the value has been set or changed.

        Returns:
            Any: value
        """
        return self._value_change_count

    @property
    def value(self):
        """Get the value if set or default otherwise.

        Returns:
            Any: value or default
        """
        if self._value is not Void:
            return self._value
        else:
            return self._field.get_default()

    @value.setter
    def value(self, v):
        """Set the value by doing cleanup.

        Falls back to default if value is invalid.

        Args:
            v (Any): value
        """
        self.set_value(v, fallback=self._field.fallback)

    def set_value(self, v, fallback=False):
        """Value setter.

        Args:
            v (Any): value
            fallback (bool, optional): Whether to fallback to default value if v is invalid. Defaults to False.
        """
        if self._value is Void:
            self._had_previous_value = False
        else:
            self._had_previous_value = True
        self._value = self._field.clean(v, fallback=fallback)
        self._value_change_count = self._value_change_count + 1 # This must be the last line
        # when the clean method raises exception, it will not be counted as
        # a successful value assignment.

    def delete_value(self):
        """Return the value to its initial state.
        """
        self._value = Void
        self._value_change_count = 0
