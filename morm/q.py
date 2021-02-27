"""Query utils.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import re
from typing import Tuple, List, Dict, Any
import collections

from morm.model import ModelType, Model


def Q(name:str) -> str:
    """SQL quote name by adding leading and trailing double quote.

    Args:
        name (str): name of table or column.

    Returns:
        str: Quoted name
    """
    return f'"{name}"'


class QueryBuilder(object):
    def __init__(self):
        self._query_str_queue = collections.deque()
        self._prepared_args = []
        self._arg_count = 0
        self._named_args = {}

    def _update_args(self, q: str, *args, **kwargs) -> str:
        self._prepared_args.extend(args)
        self._arg_count += len(args)

        self._named_args.update(kwargs)
        for k,v in self._named_args.items():
            q, mc = re.subn(f':{k}\\b', f'${self._arg_count+1}', q)
            if mc > 0:
                self._prepared_args.append(v)
                self._arg_count += 1
        return q


    def R(self, q: str, *args, **kwargs):
        q = self._update_args(q, *args, **kwargs)
        self._query_str_queue.append(q)
        return self

    def L(self, q: str, *args, **kwargs):
        q = self._update_args(q, *args, **kwargs)
        self._query_str_queue.appendleft(q)
        return self

    def get_query(self):
        """Return query string and prepared arg list

        Returns:
            tuple: (str, list) : (query, parepared_args)
        """
        return ' '.join(self._query_str_queue), self._prepared_args
