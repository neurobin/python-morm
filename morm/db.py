"""DB utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.1.0'

import collections
import re
import asyncio
from contextlib import asynccontextmanager

import asyncpg # type: ignore
from asyncpg import Record, Connection # type: ignore
from typing import Optional, List, Tuple

from morm import exceptions
from morm.model import ModelType, Model
from morm.q import Q, QueryBuilder


def record_to_model(record: Record, model_class: ModelType) -> Model:
    """Convert a Record object to Model object.

    Args:
        record (Record): Record object.
        model_class (ModelType): Model class

    Returns:
        Model: Model instance.
    """
    new_record = model_class()
    for k,v in record.items():
        setattr(new_record, k, v)
    return new_record


class Pool(object):
    def __init__(self, dsn: str = None,
                 min_size: int = 10,
                 max_size: int = 100,
                 max_queries: int = 50000,
                 max_inactive_connection_lifetime: float = 300.0,
                 setup=None,
                 init=None,
                 loop=None,
                 connection_class=Connection,
                 **connect_kwargs):
        """DB connection pool.

        The parameters are same as `asyncpg.create_pool` function.

        Args:
            dsn (str, optional): DSN string. Defaults to None.
            min_size (int, optional): Minimum connection in the pool. Defaults to 10.
            max_size (int, optional): Maximum connection in the pool. Defaults to 100.
            max_queries (int, optional): Number of queries after a connection is closed and replaced with a new connection. Defaults to 50000.
            max_inactive_connection_lifetime (float, optional): Number of seconds after which inactive connections in the pool will be closed.  Pass `0` to disable this mechanism. Defaults to 300.0.
            setup ([type], optional): A coroutine to prepare a connection right before it is returned  from `Pool.acquire()`. Defaults to None.
            init ([type], optional): A coroutine to initialize a connection when it is created. Defaults to None.
            loop ([type], optional): Asyncio even loop instance. Defaults to None.
            connection_class ([type], optional): The class to use for connections.  Must be a subclass of `asyncpg.connection.Connection`. Defaults to asyncpg.connection.Connection.
        """
        self.dsn = dsn
        self.min_size = min_size
        self.max_size = max_size
        self.max_queries = max_queries
        self.max_inactive_connection_lifetime = max_inactive_connection_lifetime
        self.setup = setup
        self.init = init
        self.loop = loop
        self.connection_class = connection_class
        self.connect_kwargs = connect_kwargs

        self._pool = None
        self.open()

    @property
    def pool(self) -> asyncpg.pool.Pool:
        """Property pool that is an asyncpg.pool.Pool object
        """
        return self._pool

    async def __create_pool(self) -> asyncpg.pool.Pool:
        """Create a asyncpg.pool.Pool for this Pool object.

        Returns:
            asyncpg.pool.Pool: Pool object (singleton)
        """
        return await asyncpg.create_pool(
                                        dsn=self.dsn,
                                        min_size=self.min_size,
                                        max_size=self.max_size,
                                        max_queries=self.max_queries,
                                        max_inactive_connection_lifetime=self.max_inactive_connection_lifetime,
                                        setup=self.setup,
                                        init=self.init,
                                        loop=self.loop,
                                        connection_class=self.connection_class,
                                        **self.connect_kwargs)
    def open(self):
        """Open the pool
        """
        if not self._pool:
            self._pool = asyncio.get_event_loop().run_until_complete(self.__create_pool())
            print("Pool opened")

    def close(self):
        """Attempt to close the pool gracefully.
        """
        if self._pool:
            asyncio.get_event_loop().run_until_complete(self._pool.close())
            self._pool = None
            print("Pool closed")


class DB(object):
    """Helper class that can execute query taking a connection from a
    connection pool defined by a Pool object.
    """

    def __init__(self, pool: Pool, con=None):
        """Initialize a DB object setting a pool to get connection from.

        If connection is given, it is used instead.

        Args:
            pool (Pool): A connection pool
            con (asyncpg.Connection): Connection. Defaults to `None`.
        """
        self._pool = pool
        self._con = con

    @property
    def pool(self) -> Pool:
        """Return the Pool object

        Returns:
            Pool: Pool object
        """
        return self._pool

    def corp(self):
        """Return the connection if available, otherwise return a Pool.

        Note: The name reads 'c or p'

        Returns:
            Connection or asyncpg.pool.Pool object
        """
        if self._con:
            return self._con
        return self._pool.pool

    async def fetch(self, query: str, *args,
                    timeout: float = None,
                    model_class: ModelType=None,
                    # con: Connection=None,
                    ):
        """Make a query and get the results.

        Resultant records can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (*list or *tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.

        Returns:
            List[Model] or List[Record] : List of model instances if model_class is given, otherwise list of Record instances.
        """
        pool = self.corp()
        records = await pool.fetch(query, *args, timeout=timeout)
        if not model_class:
            return records
        else:
            new_records = []
            for record in records:
                new_record = record_to_model(record, model_class)
                new_records.append(new_record)
            return new_records

    async def fetchrow(self, query: str, *args,
                        timeout: float = None,
                        model_class: ModelType=None,
                        # con: Connection=None,
                        ):
        """Make a query and get the first row.

        Resultant record can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (*list or *tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.

        Returns:
            Record or model_clas object or None if no rows were selected.
        """
        pool = self.corp()
        record = await pool.fetchrow(query, *args, timeout=timeout)
        if not model_class:
            return record
        else:
            if not record:
                return record
            new_record = record_to_model(record, model_class)
            return new_record

    async def fetchval(self, query: str, *args,
                        column: int = 0,
                        timeout: float = None,
                        # con: Connection=None,
                        ):
        """Run a query and return a column value in the first row.

        Args:
            query (str): Query to run.
            args (*list or *tuple): Query arguments.
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        pool = self.corp()
        return await pool.fetchval(query, *args, column=column, timeout=timeout)

    async def execute(self, query: str, *args,
                        timeout: float = None,
                        # con: Connection=None,
                        ):
        """Execute a query.

        Args:
            query (str): Query to run.
            args (*list or *tuple): Query arguments.
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            str: Status of the last SQL command
        """
        pool = self.corp()
        return await pool.execute(query, *args, timeout=timeout)

    def __call__(self, model_class: ModelType):
        return ModelQuery(self, model_class)



class ModelQuery():
    def __init__(self, db: DB, model_class: ModelType):
        self.db = db
        self.model_class = model_class
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
        query = ' '.join(self._query_str_queue)
        self._query_str_queue = collections.deque([query])
        return query, self._prepared_args

    async def fetch(self, timeout: float = None):
        """Run query method `fetch` that returns the results in model class objects

        Returns the results in model class objects

        Args:
            timeout (float, optional): Timeout in seconds. Defaults to None.

        Returns:
            List[Model]: List of model instances.
        """
        query, parepared_args = self.get_query()
        return await self.db.fetch(query, *parepared_args, timeout=timeout, model_class=self.model_class)

    async def fetchrow(self, timeout: float = None):
        """Make a query and get the first row.

        Resultant record is mapped to model_class object.

        Args:
            timeout (float, optional): Timeout value. Defaults to None.

        Returns:
            model_clas object or None if no rows were selected.
        """
        query, parepared_args = self.get_query()
        return await self.db.fetchrow(query, *parepared_args, timeout=timeout, model_class=self.model_class)

    async def fetchval(self, column: int = 0, timeout: float = None):
        """Run the query and return a column value in the first row.

        Args:
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        query, parepared_args = self.get_query()
        return await self.db.fetchval(query, *parepared_args, column=column, timeout=timeout)

    async def execute(self, timeout: float = None):
        """Execute a query and return status of the last SQL command.

        Args:
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            str: Status of the last SQL command
        """
        query, parepared_args = self.get_query()
        return await self.db.execute(query, *parepared_args, timeout=timeout)

    # async def filter(self):





class Transaction():
    def __init__(self, pool: Pool, *,
                isolation: str='read_committed',
                readonly: bool=False,
                deferrable: bool=False):
        """Start a transaction.

        Args:
            pool (Pool): Pool instance.
            isolation (str, optional): Transaction isolation mode, can be one of: `'serializable'`, `'repeatable_read'`, `'read_committed'`. Defaults to 'read_committed'. See https://www.postgresql.org/docs/9.5/transaction-iso.html
            readonly (bool, optional): Specifies whether or not this transaction is read-only. Defaults to False.
            deferrable (bool, optional): Specifies whether or not this transaction is deferrable. Defaults to False.
        """
        self.db = DB(pool)
        self.tr = None
        self.tr_args = {
            'isolation': isolation,
            'readonly': readonly,
            'deferrable': deferrable,
        }

    async def __aenter__(self) -> Connection:
        return await self.start()

    async def start(self) -> Connection:
        """Start transaction.

        Raises:
            exceptions.TransactionError: When same object is used simultaneously for transaction

        Returns:
            Connection: Connection object.
        """
        if self.db._con:
            raise exceptions.TransactionError('Another transaction is running (or not ended properly) with this Transaction object')
        self.db._con = await self.db._pool.pool.acquire() # type: ignore
        self.tr = self.db._con.transaction(**self.tr_args) # type: ignore
        await self.tr.start() # type: ignore
        # return self.db
        # test with returning con directly
        return self.db._con

    async def rollback(self):
        """Rollback the transaction.
        """
        if self.tr:
            await self.tr.rollback()

    async def commit(self):
        """Commit the transaction.
        """
        if self.tr:
            await self.tr.commit()

    async def end(self):
        """Close the transaction gracefully.

        Resources are released and some cleanups are done.
        """
        try:
            if self.db._con:
                await self.db._pool.pool.release(self.db._con)
        finally:
            self.db._con = None
            self.tr = None

    async def __aexit__(self, extype, ex, tb):
        try:
            if extype is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.end()
