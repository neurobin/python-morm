"""DB utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.1.0'


import asyncpg # type: ignore
from typing import Optional

from morm import exceptions

def Q(name:str) -> str:
    """SQL quote name by adding leading and trailing double quote.

    Args:
        name (str): name of table or column.

    Returns:
        str: Quoted name
    """
    return f'"{name}"'

class Pool(object):
    def __init__(self, dsn: str = None,
                 min_size: int = 10,
                 max_size: int = 100,
                 max_queries: int = 50000,
                 max_inactive_connection_lifetime: float = 300.0,
                 setup=None,
                 init=None,
                 loop=None,
                 connection_class=asyncpg.connection.Connection,
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
        self._pool = None
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


    async def pool(self):
        """Get a singleton pool for this Pool object.

        Returns:
            Pool: Pool object (singleton)
        """
        if not self._pool:
            # print(self.dsn)
            self._pool = await asyncpg.create_pool(
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
        return self._pool

    async def close(self):
        """Attempt to close the pool gracefully.
        """
        if self._pool:
            await self._pool.close()


class Transaction():
    def __init__(self, db, *,
                isolation='read_committed',
                readonly=False,
                deferrable=False):
        """Start a transaction.

        Args:
            db (DB): DB instance.
            isolation (str, optional): Transaction isolation mode, can be one of: `'serializable'`, `'repeatable_read'`, `'read_committed'`. Defaults to 'read_committed'. See https://www.postgresql.org/docs/9.5/transaction-iso.html
            readonly (bool, optional): Specifies whether or not this transaction is read-only. Defaults to False.
            deferrable (bool, optional): Specifies whether or not this transaction is deferrable. Defaults to False.
        """
        self.db = db
        self.pool = None
        self.con = None
        self.tr = None
        self.tr_args = {
            'isolation': isolation,
            'readonly': readonly,
            'deferrable': deferrable,
        }

    async def __aenter__(self):
        return await self.start()

    async def start(self):
        if self.con:
            raise exceptions.TransactionError('Another transaction is running (or not ended properly) with this Transaction object')
        print('Starting transaction ...')
        self.pool = await self.db.pool()
        self.con = await self.pool.acquire()
        self.tr = self.con.transaction(**self.tr_args)
        await self.tr.start()
        return self.con

    async def rollback(self):
        if self.tr:
            print('rolling back ...')
            await self.tr.rollback()

    async def commit(self):
        if self.tr:
            await self.tr.commit()

    async def end(self):
        try:
            if self.pool and self.con:
                await self.pool.release(self.con)
        finally:
            print('Transaction ended. Cleaning ...')
            self.con = None
            self.pool = None
            self.tr = None

    async def __aexit__(self, extype, ex, tb):
        print(extype)
        try:
            if extype is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.end()



class DB(object):
    """Helper class that can execute query taking a connection from a
    connection pool defined by a Pool object.
    """

    def __init__(self, pool):
        """Initialize a DB object setting a pool to get connection from.

        Args:
            pool (Pool): A connection pool
        """
        self._pool = pool

    async def pool(self):
        """Return the active connection pool.

        Returns:
            asyncpg.Pool: asyncpg.Pool object
        """
        return await self._pool.pool()

    async def get_connection_or_pool(self, connection):
        """Return the connection if given, otherwise return a Pool

        Args:
            connection (asyncpg.Connection): Connection object or None

        Returns:
            asyncpg.Connection or asyncpg.Pool: asyncpg.Pool if connection is None.
        """
        if connection:
            return connection
        else:
            return await self.pool()

    @staticmethod
    def record_to_model(record, model_class):
        new_record = model_class()
        for k,v in record.items():
            setattr(new_record, k, v)
        return new_record


    async def fetch(self, query: str, *args,
                    timeout: float = None,
                    model_class=None,
                    connection=None,
                    ):
        """Make a query and get the results.

        Resultant records can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.
            connection (asyncpg.Connection, optional): Defaults to None.

        Returns:
            list : List of records
        """
        pool = await self.get_connection_or_pool(connection)
        records = await pool.fetch(query, *args, timeout=timeout)
        if not model_class:
            return records
        else:
            new_records = []
            for record in records:
                new_record = self.__class__.record_to_model(record, model_class)
                new_records.append(new_record)
            return new_records

    async def fetchrow(self, query: str, *args,
                        timeout: float = None,
                        model_class=None,
                        connection=None,
                        ):
        """Make a query and get the first row.

        Resultant record can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.
            connection (asyncpg.Connection, optional): Defaults to None.

        Returns:
            Record or model_clas object or None if no rows were selected.
        """
        print(connection)
        pool = await self.get_connection_or_pool(connection)
        print(pool)
        record = await pool.fetchrow(query, *args, timeout=timeout)
        if not model_class:
            return record
        else:
            if not record:
                return record
            new_record = self.__class__.record_to_model(record, model_class)
            return new_record

    async def fetchval(self, query: str, *args,
                        column: int = 0,
                        timeout: float = None,
                        connection=None,
                        ):
        """Run a query and return a column value in the first row.

        Args:
            query (str): Query to run.
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.
            connection (asyncpg.Connection, optional): Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        pool = await self.get_connection_or_pool(connection)
        return await pool.fetchval(query, *args, column=column, timeout=timeout)
