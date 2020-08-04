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
    modifier function, validator function and the default and provides
    some utilities:

    `Field().clean(value, fallback=False)` provides a cleaning method.

    `Field().get_default()` gives you the default value.
    """
    def __init__(self, sql_def: str, default: Any=Void,
                 validator: Callable=always_valid,
                 modifier: Callable=nomodify):
        """Initialize the Field object.

        Args:
            sql_def (str): SQL definition of the model Field
            default (Any, optional): Default value (can be a callable). Defaults to Void.
            validator (callable, optional): A callable that accepts exactly one argument. Validates the value in `clean` method. Defaults to always_valid.
            modifier (callable, optional): A callable that accepts exactly one argument. Modifies the value before passing it to `validator` when the `clean` method is called.. Defaults to nomodify.
        """
        self.sql_def = sql_def
        self.default = default
        self.validator = validator
        self.modifier = modifier
        self.name = ''

    def clean(self, value: Any, fallback: bool=False):
        """Clean the value by calling modifier then validator.

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
        value = self.modifier(value)
        if not self.validator(value):
            if fallback:
                return self.get_default()
            raise ValueError("Value did not pass validation check for '%s'" % (self.name,))
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
