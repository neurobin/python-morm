"""DB utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import asyncpg


class Pool(object):
    def __init__(self, dsn=None,
                 min_size=10,
                 max_size=100,
                 max_queries=50000,
                 max_inactive_connection_lifetime=300.0,
                 setup=None,
                 init=None,
                 loop=None,
                 connection_class=asyncpg.connection.Connection,
                 **connect_kwargs):
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

    async def new_connection(self):
        """Get a new connection from the pool.

        Multiple call may or may not return the same connection.

        Returns:
            asyncpg.Connection: asyncpg.Connection object
        """
        pool = await self.pool()
        return await pool.acquire()

    async def close(self):
        if self._pool:
            await self._pool.close()


class DB(object):
    """Helper class that can execute query taking a connection from a
    connection pool defined by a Pool object.
    """

    def __init__(self, pool):
        """Return a DB object setting a pool to get connection from.

        Args:
            pool (Pool): A connection pool
        """
        self._pool = pool
        self._con = None


    async def con(self):
        """Return the singleton connection of this db object.

        Returns:
            asyncpg.Connection: asyncpg.Connection object
        """
        if not self._con:
            self._con = await self._pool.new_connection()
        return self._con

    async def execute(self, query: str, *args, timeout: float = None) -> str:
        """Make a query using a singleton connection retrieved from a
        pool of connection.

        This makes a prepared query. Example:

        ```python
        await con.execute('INSERT INTO mytab (a) VALUES ($1), ($2), 10, 20)
        ```

        Args:
            query (str): Query string
            args (tuple): Query arguments
            timeout (float, optional): Timeout value. Defaults to None.

        Returns:
            str: 	Status of the last SQL command
        """
        con = await self.con()
        return await con.execute(query, *args, timeout=timeout)

    async def select(self, query: str, *args,
                    timeout: float = None,
                    model_class=None,
                    ):
        """Make a select query and get the results.

        Resultant records can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (class, optional): A model class. Defaults to None.

        Returns:
            list : List of records
        """
        con = await self.con()
        records = await con.fetch(query, *args, timeout=timeout)
        if not model_class:
            return records
        else:
            new_records = []
            for record in records:
                new_record = model_class()
                for k,v in record.items():
                    setattr(new_record, k, v)
                new_records.append(new_record)
            return new_records

    async def select_first(self, query: str, *args,
                        timeout: float = None,
                        model_class=None,
                        ):
        """Make a select query and get the first row.

        Resultant record can be mapped to model_class objects.

        Args:
            query (str): Query string.
            args (list or tuple): Query arguments.
            timeout (float, optional): Timeout value. Defaults to None.
            model_class (class, optional): A model class. Defaults to None.

        Returns:
            Record or model_clas object or None if no rows were selected.
        """
        con = await self.con()
        record = await con.fetchrow(query, *args, timeout=timeout)
        if not model_class:
            return record
        else:
            if not record:
                return record
            new_record = model_class()
            for k,v in record.items():
                setattr(new_record, k, v)
            return new_record
