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
from morm.model import ModelType, Model, ModelBase
from morm.q import Q, QueryBuilder
from morm.types import Void


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
        new_record.Meta._fromdb_.append(k)
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

    def __call__(self, model_or_object: ModelType = None):
        """Return a ModelQuery for model or ObjectQuery for object

        If None is passed it will give a ModelQuery without setting
        self.model

        Args:
            model_or_object (ModelType, optional): model class or model object. Defaults to None.

        Raises:
            TypeError: If invalid model type or object type is passed

        Returns:
            ModelQuery|ObjectQuery
        """
        if isinstance(model_or_object, ModelType) or model_or_object is None:
            return ModelQuery(self, model_or_object)
        elif isinstance(model_or_object, ModelBase):
            return ObjectQuery(ModelQuery(self, model_or_object.__class__), model_or_object)
        raise TypeError(f"Invalid model or model object: {model_or_object}")



class ModelQuery():
    def __init__(self, db: DB, model_class: ModelType):
        """Query builder for model class.

        The `q` family of methods (`q, qc, qu etc..`) can be used to
        build a query step by step. These methods can be chained
        together to break down the query building in multiple steps.

        Several properties are available to get information of the model
        such as table name (`self.table`), ordering (`self.ordering`),
        field names (`self.f.<field_name>`) etc..

        `self.c` is a counter that gives an integer representing the
        last existing argument position plus 1.

        `reset()` can be called to reset the query to start a new.

        To execute a query, you need to run one of the execution methods
        : `fetch, fetchrow, fetchval, execute`.

        Notable convenience methods:

        * `update(data)`: Initialize a update query for data
        * `filter()`: Initialize a filter query upto WHERE clasue.
        * `get(pkval)`: Get an item by primary key.

        Args:
            db (DB): DB object
            model_class (ModelType): model
        """
        self.reset()
        self.db = db
        self.model = model_class # can be None
        self._f = None # no reset
        self._f_ = None # no reset

    def reset(self):
        """Reset the model query by returning it to its initial state.

        Returns:
            self (Enables method chaining)
        """
        self._query_str_queue = []
        self.end_query_str = ''
        self.start_query_str = ''
        self._prepared_args = []
        self._arg_count = 0
        self._named_args = {}
        self._named_args_mapper = {}
        self.__filter_initiated = False
        self._ordering = ''
        self.__update_initiated = False
        return self


    @property
    def c(self):
        """Current available argument position in the query

        arg_count + 1 i.e if $1 and $2 has been used so far, then
        self.c is 3 so that you can use it to make $3.

        Returns:
            self
        """
        return self._arg_count + 1

    @property
    def table(self):
        """Table name of the model
        """
        return self.model._get_db_table_()

    @property
    def table_(self):
        """Table name of the model (quoted)
        """
        return Q(self.model._get_db_table_())

    @property
    def pk(self):
        """Primary key name
        """
        return self.model._get_pk_()

    @property
    def pk_(self):
        """Primary key name (quoted)
        """
        return Q(self.model._get_pk_())

    @property
    def ordering(self):
        """Ordering query in SQL, does not include `ORDER BY`.

        Example: `"price" ASC, "quantity" DESC`
        """
        if not self._ordering:
            self._ordering = ','.join([' '.join(y) for y in self.model._get_ordering_(quote='"')])
        return self._ordering

    def _get_GetFieldName_object(self, func):
        class _GetFieldName():
            def __getattr__(self, k):
                return func(k)

            def __setattr__(self, k, v):
                raise NotImplementedError
        return _GetFieldName()


    @property
    def f(self):
        """Field name container

        It can be used to avoid spelling mistakes in writing query.
        Example:

        query: `'select "profesion" from "table_name"'`

        will only produce error after actually running the query against
        a correctly spelled column 'profession'.

        while,

        query: `f'select "{self.fn.profesion}" from "{self.table}"'`

        will throw python exception telling you that there is no
        misspelled 'profesion' field.

        Note: you have to change `self` in above to the current
        ModelQuery instance

        """
        if not self._f:
            def func(k):
                return self.model._get_field_name_(k)
            self._f = self._get_GetFieldName_object(func)
        return self._f

    @property
    def f_(self):
        """Field name container where names are quoted.
        """
        if not self._f_:
            def func(k):
                return self.model._get_field_name_(Q(k))
            self._f = self._get_GetFieldName_object(func)
        return self._f_

    def _process_positional_args(self, *args):
        if args:
            self._prepared_args.extend(args)
            self._arg_count += len(args)


    def _process_keyword_args(self, q: str, **kwargs) -> str:
        # TODO: improvents need to be done
        # 1. needs to handle only unquoted keyword :field_name
        #    and ignore ':field_name' or ":field_name"
        self._named_args.update(kwargs)
        for k,v in self._named_args.items():
            if k in self._named_args_mapper:
                q, mc = re.subn(f':{k}\\b', f'${self._named_args_mapper[k]}', q)
            else:
                q, mc = re.subn(f':{k}\\b', f'${self._arg_count+1}', q)
                if mc > 0:
                    self._prepared_args.append(v)
                    self._arg_count += 1
                    self._named_args_mapper[k] = self._arg_count
        return q

    def q(self, q: str, *args):
        """Add raw query stub without parsing to check for keyword arguments

        Use `$1`, `$2` etc. for prepared arguments.

        Use `self.c` (instance property, use fstring) to get the current
        available prepared argument position.

        This is an efficient way to add query that do not have any
        keyword arguments to handle, compared to `q_()` which checks for
        keyword arguments everytime it is called.

        Example:

        ```python
        mq = db(SomeModel)
        mq\
        .q('SELECT * FROM "table" WHERE $1', True)\
        .q('AND "price" >= $2', 33)\
        .q(f'OR "price" = ${mq.c}', 0) # mq.c=3 (now)\
        .q_('OR "status" = :status', status='OK')\
        # :status is $4:
        .q('OR "active" = $5', 0)\
        .q_('AND "status" = :status')\
        # status='OK' from previous call
        .q('OR "price" = $2')\
        # $2=33 from previous call
        #using format string and mq.c to get the argument position:
        .q(f'OR "price" > ${mq.c} OR "quantity" > ${mq.c+1}', 12, 3)
        #               mq.c=6 ^
        ```

        Args:
            q (str): raw query string

        Returns:
            ModelQuery: self, enables method chaining.
        """
        self._process_positional_args(*args)
        self._query_str_queue.append(q)
        return self


    def q_(self, q: str, *args, **kwargs):
        """Add a query stub having keyword params.

        Use the format `:field_name` for keyword parameter.
        `:field_name` is converted to positional parameter (`$n`).

        This method checks the query against all keyword arguments
        that has been added so far with other `q*()` methods.

        Args:
            q (str): query string (SQL)

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        self._process_positional_args(*args)
        q = self._process_keyword_args(q, **kwargs)
        self._query_str_queue.append(q)
        return self

    def qq(self, word: str):
        """Quote and add a word to the query.

        Enable to add names with auto-quote. For example, if the name
        for a field value is `status`, it can be added to the query
        with auto-quoting, i.e for postgresql it will be added
        as `"status"`.

        Example:

        ```python
        .qq('price').q('>= $1',34)
        ```

        Args:
            word (str): the word that needs to be added with quote.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        if word:
            self._query_str_queue.append(Q(word))
        return self


    def qc(self, word: str, rest: str, *args):
        """Add query by quoting `word` while adding the `rest` as is.

        This is a shorthand for making where clause conditions.
        For example: `qc('price', '>=$1', 34)` is a safe way to write
        a where condition like: `"price" >=34`.

        The same can be achieved by using a combination of
        `qq()` and `q()` or manually quoting and using
        with `q()`

        Example:

        ```python
        .qc('price', '>= $1', 34)
        ```

        Args:
            word (str): left part of query that needs to be quoted
            rest (str): right part of query that does not need to be quoted
            *args (any): prepared args

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.qq(word).q(rest, *args)


    def qc_(self, word: str, rest: str, *args, **kwargs):
        """Add query by quoting `word` while adding the `rest` as is.

        Same as `qc()` except this method parses the `rest` query string
        for keyword params in the format: `:field_name`

        Args:
            word (str): left part of query that needs to be quoted
            rest (str): right part of query that does not need to be quoted
            *args (any): prepared args
            *kwargs: prepared keyword args

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.qq(word).q_(rest, *args, **kwargs)

    def qo(self, order: str):
        """Convert `-field_name,` to proper order_by criteria and add to query.

        Example: `-field_name,` will become: `"field_name" DESC,`

        * `+` at beginning means ascending order (default)
        * `-` at beginning means descending order
        * `,` at end means you will add more order criteria

        Ommit the comma (`,`) when it is the last ordering criteria.

        Args:
            order (str): order criteria in the format `+/-field_name,`

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        direction = 'ASC'
        if order.startswith('-'):
            order = order[1:]
            direction = 'DESC'
        elif order.startswith('+'):
            order = order[1:]
        if order.endswith(','):
            order = order[0:-1]
            direction += ','
        return self.qq(order).q(direction)

    def qu(self, data: dict):
        """Convert data to "column"=$n query with prepared args as the
            values and add to the main query.

        The counter of positional arguments increases by the number of
        items in `data`. Make use of `self.c` counter to add more
        queries after using this method.

        Args:
            data (dict): data in format: `{'column': value}`

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        setq = ', '.join([f'"{c}"=${i}' for i,c in enumerate(data, self.c)])
        return self.q(setq, *data.values())

    def qreturning(self, *args):
        """Convenience to add a `RETURNING` clause.

        Args:
            args: column names.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        q = '","'.join(args)
        if q:
            q = f'"{q}"'
        return self.q(q)

    def qwhere(self):
        """Convenience to add 'WHERE' to the main query.

        Make use of `qc()` method to add conditions.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.q('WHERE')


    def getq(self):
        """Return query string and prepared arg list

        Returns:
            tuple: (str, list) : (query, parepared_args)
        """
        query = ' '.join(self._query_str_queue)
        self._query_str_queue = [query]
        query = f'{self.start_query_str} {query} {self.end_query_str}'
        return query, self._prepared_args

    async def fetch(self, timeout: float = None):
        """Run query method `fetch` that returns the results in model class objects

        Returns the results in model class objects.

        Args:
            timeout (float, optional): Timeout in seconds. Defaults to None.

        Returns:
            List[Model]: List of model instances.
        """
        query, parepared_args = self.getq()
        return await self.db.fetch(query, *parepared_args, timeout=timeout, model_class=self.model)

    async def fetchrow(self, timeout: float = None):
        """Make a query and get the first row.

        Resultant record is mapped to model_class object.

        Args:
            timeout (float, optional): Timeout value. Defaults to None.

        Returns:
            model_clas object or None if no rows were selected.
        """
        query, parepared_args = self.getq()
        return await self.db.fetchrow(query, *parepared_args, timeout=timeout, model_class=self.model)

    async def fetchval(self, column: int = 0, timeout: float = None):
        """Run the query and return a column value in the first row.

        Args:
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        query, parepared_args = self.getq()
        return await self.db.fetchval(query, *parepared_args, column=column, timeout=timeout)

    async def execute(self, timeout: float = None):
        """Execute the query.

        Args:
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            str: Status of the last SQL command
        """
        query, parepared_args = self.getq()
        return await self.db.execute(query, *parepared_args, timeout=timeout)

    def filter(self, no_ordering=False):
        """Initiate a filter.

        This initiates a `SELECT` query upto `WHERE`. You can then use the
        `qc()` method to add conditions and finally execute the `fetch()`
        method to get all results or execute the `fetchrow()` method
        to get single row.

        Example:

        ```python
        .filter().qc('price', '>=$1 AND', 45).qc('status', '=$1')
        ```

        Args:
            no_ordering (bool): Whether to remove the default ordering SQL. Defaults to `False`.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        if not self.__filter_initiated:
            down_fields = ','.join([Q(x) for x in self.model._get_fields_(up=False)])
            self.q(f'SELECT {down_fields} FROM "{self.model._get_db_table_()}" WHERE')
            self.__filter_initiated = True
            order_by = self.ordering
            if order_by and not no_ordering:
                self.end_query_str = f'ORDER BY {order_by}'
        else:
            ValueError(f"Filter is already initiated for this {self.__class__.__name__} query object: {self}")
        return self

    async def get(self, *vals, col='', comp='=$1'):
        """Get the first row found by column and value.

        If `col` is not given, it defaults to the primary key (`pk`) of
        the model.

        If comparison is not given, it defaults to `=$1`

        Args:
            *vals (any): Values to compare. Must be referenced with $1, $2 etc.. in `comp`.
            col (str, optional): Column name. Defaults to the primary key.
            comp (str, optional): Comparison. Defaults to '=$1'.

        Returns:
            model_clas object or None if no rows were selected.
        """
        if not col:
            col = self.model.Meta.pk
        return await self.filter().qc(col, comp, *vals).fetchrow()


    def update(self, data: dict):
        """Initiate a UPDATE query for data.

        This initiates an `UPDATE` query upto `WHERE` and leaves you to
        add conditions with other methods such as `qc` or the generic
        method `q()`.

        Finally call the `execute()` method to execute the query or
        call the `fetchval()` method if using `RETURNING` clause.

        Args:
            data (dict): data in key value dictionary

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        if not self.__update_initiated:
            self.q(f'UPDATE {self.table} SET').qu(data).qwhere()
            self.__update_initiated = True
        else:
            ValueError(f"update is already initiated for this {self.__class__.__name__} query: {self}")
        return self



class ObjectQuery():
    def __init__(self, mq: ModelQuery, mob: ModelBase):
        """Initiate object query

        Args:
            mq (ModelQuery): ModelQuery object
            mob (ModelBase): Model object
        """
        self.mq = mq
        self.mob = mob
        self.model = self.mq.model
        self.DATA_NO_CHANGE = 'DATA_NO_CHANGE_TRIGGERED'

    def get_insert_query(self):
        """Get insert query for the model object with the current data

        Returns:
            (str, list): query, prepared_args
        """
        data = self.mob.Meta._fields_
        new_data_gen = self.model._get_FieldValue_data_valid_(data, up=True)
        columns = []
        values = []
        markers = []
        c = 0
        for n,v in new_data_gen:
            c += 1
            columns.append(n)
            values.append(v.value)
            markers.append(f'${c}')

        column_q = '","'.join(columns)
        if column_q:
            column_q = f'"{column_q}"'
        marker_q = ', '.join(markers)
        if column_q:
            query = f'INSERT INTO "{self.mq.table}" ({column_q}) VALUES ({marker_q}) RETURNING "{self.mq.pk}"'
        else:
            query = ''
        return query, values

    def get_update_query(self):
        """Get the update query for the changed data in the model object

        Raises:
            AttributeError: If primary key does not exists i.e if not updatable

        Returns:
            str, args: tuple of query, prepared_args
        """
        pkval = getattr(self.mob, self.mq.pk) #save method depends on it's AttributeError
        data = self.mob.Meta._fields_
        new_data_gen = self.model._get_FieldValue_data_valid_(data, up=True)
        colval = []
        values = []
        c = 0
        for n,v in new_data_gen:
            if n == self.mq.pk: continue
            if n in self.mob.Meta._fromdb_:
                countover = 1
            else:
                countover = 0
            if v.value_change_count > countover:
                c += 1
                colval.append(f'"{n}"=${c}')
                values.append(v.value)
                v._value_change_count = 0

        where = f'"{self.mq.pk}"=${c+1}'
        values.append(pkval)

        colval_q = ', '.join(colval)
        if colval_q:
            query = f'UPDATE "{self.mq.table}" SET {colval_q} WHERE {where}'
        else:
            query = ''
        return query, values


    async def insert(self):
        """Insert the current data state into db

        Returns:
            Value of primary key of the inserted row
        """
        query, args = self.get_insert_query()
        pkval = await self.mq.db.fetchval(query, *args)
        if pkval is not None:
            setattr(self.mob, self.mq.pk, pkval)
        return pkval

    async def update(self):
        """Update the current changed data onto db

        Raises:
            AttributeError: If primary key does not exists.

        Returns:
            str: status of last sql command
        """
        query, args = self.get_update_query()
        if query:
            return await self.mq.db.execute(query, *args)
        return self.DATA_NO_CHANGE


    async def save(self):
        """Insert if not exists and update if exists.

        update is tried first, if fails, insert is called.

        Returns:
            int or str: The value of the primary key for insert or
                            status for update operation.
        """
        try:
            return await self.update()
        except AttributeError:
            return await self.insert()








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
