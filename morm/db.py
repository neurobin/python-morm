"""DB utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.1.0'


import asyncpg # type: ignore
from asyncpg import Record, Connection # type: ignore
from typing import Optional, List

from morm import exceptions
from morm.model import _ModelMeta_, Model

def Q(name:str) -> str:
    """SQL quote name by adding leading and trailing double quote.

    Args:
        name (str): name of table or column.

    Returns:
        str: Quoted name
    """
    return f'"{name}"'


def record_to_model(record: Record, model_class: _ModelMeta_) -> Model:
    """Convert a Record object to Model object.

    Args:
        record (Record): Record object.
        model_class (_ModelMeta_): Model class

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


    async def pool(self) -> asyncpg.pool.Pool:
        """Get a singleton pool for this Pool object.

        Returns:
            asyncpg.pool.Pool: Pool object (singleton)
        """
        if not self._pool:
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
            self._pool = None


class DB(object):
    """Helper class that can execute query taking a connection from a
    connection pool defined by a Pool object.
    """

    def __init__(self, pool: Pool):
        """Initialize a DB object setting a pool to get connection from.

        Args:
            pool (Pool): A connection pool
        """
        self._pool = pool

    async def pool(self) -> asyncpg.pool.Pool:
        """Return the active connection pool.

        Returns:
            asyncpg.pool.Pool: asyncpg.pool.Pool object
        """
        return await self._pool.pool()

    async def get_connection_or_pool(self, con):
        """Return the connection if given, otherwise return a Pool.

        Args:
            con (Connection): Connection object or None

        Returns:
            Connection or asyncpg.pool.Pool object
        """
        if con:
            return con
        else:
            return await self.pool()

    async def fetch(self, query: str, *args,
                    timeout: float = None,
                    model_class: _ModelMeta_=None,
                    con: Connection=None,
                    ):
        """Make a query and get the results.

        Resultant records can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.
            con (Connection, optional): Defaults to None.

        Returns:
            List[Model] or List[Record] : List of model instances if model_class is given, otherwise list of Record instances.
        """
        pool = await self.get_connection_or_pool(con)
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
                        model_class: _ModelMeta_=None,
                        con: Connection=None,
                        ):
        """Make a query and get the first row.

        Resultant record can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (Model, optional): Defaults to None.
            con (asyncpg.Connection, optional): Defaults to None.

        Returns:
            Record or model_clas object or None if no rows were selected.
        """
        pool = await self.get_connection_or_pool(con)
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
                        con: Connection=None,
                        ):
        """Run a query and return a column value in the first row.

        Args:
            query (str): Query to run.
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.
            con (asyncpg.Connection, optional): Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        pool = await self.get_connection_or_pool(con)
        return await pool.fetchval(query, *args, column=column, timeout=timeout)



class Transaction():
    def __init__(self, db: DB, *,
                isolation: str='read_committed',
                readonly: bool=False,
                deferrable: bool=False):
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

    async def __aenter__(self) -> Connection:
        return await self.start()

    async def start(self) -> Connection:
        """Start transaction.

        Raises:
            exceptions.TransactionError: When same object is used simultaneously for transaction

        Returns:
            Connection: Connection object.
        """
        if self.con:
            raise exceptions.TransactionError('Another transaction is running (or not ended properly) with this Transaction object')
        self.pool = await self.db.pool()
        self.con = await self.pool.acquire() # type: ignore
        self.tr = self.con.transaction(**self.tr_args) # type: ignore
        await self.tr.start() # type: ignore
        return self.con

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
            if self.pool and self.con:
                await self.pool.release(self.con)
        finally:
            self.con = None
            self.pool = None
            self.tr = None

    async def __aexit__(self, extype, ex, tb):
        try:
            if extype is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.end()
