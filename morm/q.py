"""Query utils.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import re
from typing import Optional, Dict, List, Tuple, TypeVar, Union, Any
import collections

from morm.model import ModelType, Model


def Q(name: str, quote: str = '"') -> str:
    """Quote name by adding leading and trailing (double) quote.

    Args:
        name (str): name of table or column.
        quote (str): str to quote with.

    Returns:
        str: Quoted name
    """
    return f'{quote}{name}{quote}'
