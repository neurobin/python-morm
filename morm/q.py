"""Query utils.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import re
from typing import Tuple, List, Dict, Any

from morm.model import ModelType, Model


def Q(name:str) -> str:
    """SQL quote name by adding leading and trailing double quote.

    Args:
        name (str): name of table or column.

    Returns:
        str: Quoted name
    """
    return f'"{name}"'


class QueryBuilder():
    def __init__(self, func, model: ModelType):
        self._func = func
        self._model = model
        self._query: List[str] = []
        self._prepared_args: List[Any] = []
        self._named_args: Dict[str, Any] = {}

    async def run(self, **kwargs):
        """Run a query function with this query builder

        Args:
            kwargs: Other arguments that should be passed to the query function

        Returns:
            Any: query result
        """
        query, prepared_args = self._get_query_args()
        return await self._func(query, *prepared_args, model_class=self._model, **kwargs)


    def r(self, *args):
        """Append query string/s to query builder

        Args:
             (str): query string

        Returns:
            QueryBuilder: self
        """
        self._query.extend(args)
        return self

    def q(self, *args):
        """Append query strings to query builder by quoting them.

        Returns:
            QeuryBuilder: self
        """
        args = [Q(x) for x in args]
        self._query.extend(args)
        return self


    def _get_query_args(self):
        """Return the total query string along with the prepared args

        Returns:
            str, list: query string, prepared args
        """
        prepared_args = list(self._prepared_args)
        s = ''.join(self._query)
        # c = len(prepared_args)
        # i = c
        # for k, v in self._named_args.items():
        #     pat = f"[:]{k}\\b"
        #     if re.search(pat, s):
        #         i = i + 1
        #         prepared_args.append(v)
        #         s = re.sub(pat, f"${i}", s)
        return s, prepared_args


    def args(self, *args):
        """Add prepared arguments to query builder.
        """
        self._prepared_args.extend(args)
        return self

    def nargs(self, *args, **kwargs):
        """Add named arguments to query builder

        This works by converting the named arguments to positional arguments.

        Use: Add a colon before the name to reference it, e.g: :birthday

        Args:
            args: Dictionaries containg the name and values
            kwargs: keyword args with name value

        Returns:
            QueryBuilder: self
        """
        for arg in args:
            self._named_args.update(arg)
        self._named_args.update(kwargs)
        return self




class SelectQuery(QueryBuilder):
    def __init__(self, func, model: ModelType):
        super().__init__(func, model)
        self._what_sql = '*'
        self._where_sql = 'true'

    def what(self, what_sql):
        self._what_sql = what_sql
        return self

    def where(self, where_sql):
        self._where_sql = where_sql
        return self

    async def run(self, **kwargs):
        self.r('SELECT ', self._what_sql, ' FROM ', Q(self._model.Meta.db_table), ' WHERE ', self._where_sql)
        return await super().run(**kwargs)
