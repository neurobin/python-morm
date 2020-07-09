"""Field class.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'

from typing import Any, Optional
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
