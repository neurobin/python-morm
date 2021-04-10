"""DB utilities.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.1.0'

import collections
import re
import asyncio
import nest_asyncio  # type: ignore
import atexit
import logging

import asyncpg # type: ignore
from asyncpg import Record, Connection # type: ignore
from typing import Optional, Dict, List, Tuple, TypeVar, Union, Any

from morm import exceptions
from morm.model import ModelType, Model, ModelBase, _FieldNames
from morm.q import Q
from morm.types import Void

LOGGER_NAME = 'morm.db-'
log = logging.getLogger(LOGGER_NAME)


nest_asyncio.apply()

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
        new_record.Meta._fromdb_.append(k)
        setattr(new_record, k, v)
    return new_record


class Pool(object):
    """Open database connection pool.

    ```python
    from morm.db import Pool

    DB_POOL = Pool(
        dsn='postgres://',
        host='localhost',
        port=5432,
        user='jahid',       # change accordingly
        password='jahid',   # change accordingly
        database='test',    # change accordingly
        min_size=10,        # change accordingly
        max_size=90,        # change accordingly
    )
    ```

    This will create and open an asyncpg pool which will be automatically closed at exit.

    You should set this in a settings file from where you can import the `DB_POOL`

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
        self._open()
        atexit.register(self._close)

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
    def _open(self):
        """Open the pool. Called on init so not need to call this
        method explicitly.
        """
        if not self._pool:
            self._pool = asyncio.get_event_loop().run_until_complete(self.__create_pool())
            log.debug("Pool opened")

    def _close(self):
        """Attempt to close the pool gracefully. registered with atexit.
        You do not need to call this method explicitly.
        """
        if self._pool:
            asyncio.get_event_loop().run_until_complete(self._pool.close())
            self._pool = None
            log.debug("Pool closed")


class DB(object):
    """Initialize a DB object setting a pool to get connection from.

    If connection is given, it is used instead.

    The `corp()` method returns an asyncpg.pool.Pool or an
    asyncpg.Connection

    Args:
        pool (Pool): A connection pool
        con (Connection): Connection. Defaults to None.
    """

    def __init__(self, pool: Pool, con: Connection=None):
        self._pool = pool
        self._con = con
        self.DATA_NO_CHANGE = 'DATA_NO_CHANGE_TRIGGERED'

    def corp(self) -> Union[asyncpg.pool.Pool, Connection]:
        """Return the connection if available, otherwise return a Pool.

        Note: The name reads 'c or p'

        Returns:
            asyncpg.Connection or asyncpg.pool.Pool object
        """
        if self._con:
            return self._con
        return self._pool.pool

    async def fetch(self, query: str, *args,
                    timeout: float = None,
                    model_class: ModelType=None
                    ) -> Union[List[ModelBase], List[Record]]:
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
                        model_class: ModelType=None
                        ) -> Union[ModelBase, Record]:
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
                        timeout: float = None
                        ) -> Any:
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
                        timeout: float = None
                        ) -> str:
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

    def get_insert_query(self, mob: ModelBase, reset=False) -> Tuple[str, List[Any]]:
        """Get insert query for the model object (mob) with its current data

        Args:
            mob (ModelBase): Model object
            reset (bool): Reset the value change counter. Defaults to False

        Returns:
            (str, list): query, args
        """
        data = mob.Meta._fields_
        new_data_gen = mob.__class__._get_FieldValue_data_valid_(data, up=True)
        columns = []
        values = []
        markers = []
        c = 0
        for n,v in new_data_gen:
            c += 1
            if reset:
                v.value_change_count = 0
                mob.Meta._fromdb_ = []
            columns.append(n)
            values.append(v.value)
            markers.append(f'${c}')
        column_q = '","'.join(columns)
        if column_q:
            column_q = f'"{column_q}"'
            marker_q = ', '.join(markers)
            query = f'INSERT INTO "{mob.__class__._get_db_table_()}" ({column_q}) VALUES ({marker_q}) RETURNING "{mob.__class__._get_pk_()}"'
        else:
            query = ''
        return query, values

    def get_update_query(self, mob: ModelBase, reset=False) -> Tuple[str, List[Any]]:
        """Get the update query for the changed data in the model object (mob)

        Args:
            mob (ModelBase): Model object
            reset (bool): If True, this method can be called just once to get the changes done on mob. Subsequent call will return empty query.

        Raises:
            AttributeError: If primary key does not exists i.e if not updatable

        Returns:
            str, args: tuple of query, args
        """
        pkval = getattr(mob, mob.__class__._get_pk_()) #save method depends on it's AttributeError
        data = mob.Meta._fields_
        new_data_gen = mob.__class__._get_FieldValue_data_valid_(data, up=True)
        colval = []
        values = []
        c = 0
        for n,v in new_data_gen:
            if n == mob.__class__._get_pk_(): continue
            if v.value_change_count > 0:
                c += 1
                colval.append(f'"{n}"=${c}')
                values.append(v.value)
                if reset:
                    v.value_change_count = 0
        colval_q = ', '.join(colval)
        if colval_q:
            where = f'"{mob.__class__._get_pk_()}"=${c+1}'
            values.append(pkval)
            query = f'UPDATE "{mob.__class__._get_db_table_()}" SET {colval_q} WHERE {where}'
        else:
            query = ''
        return query, values

    def get_delete_query(self, mob: ModelBase) -> Tuple[str, List[Any]]:
        """Get the delete query for the model object.

        Args:
            mob (ModelBase): model object.

        Returns:
            Tuple[str, List[Any]]: quey, args
        """
        pkval = getattr(mob, mob.__class__._get_pk_())
        query = f'DELETE FROM "{mob.__class__._get_db_table_()}" WHERE "{mob.__class__._get_pk_()}"=$1'
        return query, [pkval]

    async def delete(self, mob: ModelBase, timeout: float = None) -> str:
        """Delete the model object data from database.

        Args:
            mob (ModelBase): Model object
            timeout (float): timeout value. Defaults to None.

        Returns:
            (str): status of last sql command.
        """
        query, args = self.get_delete_query(mob)
        await mob._pre_delete_(self)
        res = await self.execute(query, *args, timeout=timeout)
        await mob._post_delete_(self)
        return res

    async def insert(self, mob: ModelBase, timeout: float = None) -> Any:
        """Insert the current data state of mob into db.

        Args:
            mob (ModelBase): Model object
            timeout (float): timeout value. Defaults to None.

        Returns:
            (Any): Value of primary key of the inserted row
        """
        query, args = self.get_insert_query(mob, reset=True)
        await mob._pre_insert_(self)
        pkval = await self.fetchval(query, *args, timeout=timeout)
        if pkval is not None:
            setattr(mob, mob.__class__._get_pk_(), pkval)
        await mob._post_insert_(self)
        return pkval

    async def update(self, mob: ModelBase, timeout: float = None) -> str:
        """Update the current changed data of mob onto db

        Args:
            mob (ModelBase): Model object
            timeout (float): timeout value. Defaults to None.

        Raises:
            AttributeError: If primary key does not exists.

        Returns:
            str: status of last sql command.
            Successful status starts with the word 'UPDATE' followed by
            number of rows updated, which should be 1 in this case.
        """
        query, args = self.get_update_query(mob, reset=True)
        if query:
            await mob._pre_update_(self)
            res = await self.execute(query, *args, timeout=timeout)
            await mob._post_update_(self)
        else:
            res = self.DATA_NO_CHANGE
        return res


    async def save(self, mob: ModelBase, timeout: float = None) -> Union[str, Any]:
        """Insert if not exists and update if exists.

        update is tried first, if fails (if pk does not exist), insert
        is called.

        Args:
            mob (ModelBase): Model object
            timeout (float): timeout value. Defaults to None.

        Returns:
            int or str: The value of the primary key for insert or
                            status for update.
        """
        await mob._pre_save_(self)
        try:
            res = await self.update(mob, timeout=timeout)
        except AttributeError:
            res = await self.insert(mob, timeout=timeout)
        await mob._post_save_(self)
        return res

    def q(self, model: ModelType = None) -> 'ModelQuery':
        """Return a ModelQuery for model

        If `None` is passed, it will give a `ModelQuery` without setting
        `self.model` on the `ModelQuery` object.

        Args:
            model (ModelType, optional): model class. Defaults to None.

        Raises:
            TypeError: If invalid model type is passed

        Returns:
            ModelQuery: ModelQuery object
        """
        return self(model)


    def __call__(self, model: ModelType = None) -> 'ModelQuery':
        """Return a ModelQuery for model

        If `None` is passed, it will give a `ModelQuery` without setting
        `self.model` on the `ModelQuery` object.

        Args:
            model (ModelType, optional): model class. Defaults to None.

        Raises:
            TypeError: If invalid model type is passed

        Returns:
            ModelQuery: ModelQuery object
        """
        if isinstance(model, ModelType) or model is None:
            return ModelQuery(self, model)
        raise TypeError(f"Invalid model: {model}. model must be of type {ModelType.__name__}. Make sure you did not pass a model object by mistake.")



class ModelQuery():
    """Query builder for model class.

    Calling `db(Model)` gives you a model query handler which have several query methods to help you make queries.

    Use `q(query, *args)` method to make queries with positional arguments. If you want named arguments, use the uderscored version of these methods. For example, `q(query, *args)` has an underscored version `q_(query, *args, **kwargs)` that can take named arguments.

    You can add a long query part by part:

    ```python
    from morm.db import DB

    db = DB(DB_POOL) # get a db handle.
    qh = db(User)   # get a query handle.

    query, args = qh.q(f'SELECT * FROM {qh.db_table}')\
                    .q(f'WHERE {qh.f.profession} = ${qh.c}', 'Teacher')\
                    .q_(f'AND {qh.f.age} = :age', age=30)\
                    .getq()
    print(query, args)
    # fetch:
    await qh.fetch()
    ```

    The `q` family of methods (`q, qc, qu etc..`) can be used to
    build a query step by step. These methods can be chained
    together to break down the query building in multiple steps.

    Several properties are available to get information of the model
    such as:

    1. `qh.db_table`: Quoted table name e.g `"my_user_table"`.
    2. `qh.pk`: Quoted primary key name e.g `"id"`.
    3. `qh.ordering`: ordering e.g `"price" ASC, "quantity" DESC`.
    4. `qh.f.<field_name>`: quoted field names e.g`"profession"`.
    5. `qh.c`: Current available position for positional argument (Instead of hardcoded `$1`, `$2`, use `f'${qh.c}'`, `f'${qh.c+1}'`).

    `qh.c` is a counter that gives an integer representing the
    last existing argument position plus 1.

    `reset()` can be called to reset the query to start a new.

    To execute a query, you need to run one of the execution methods
    : `fetch, fetchrow, fetchval, execute`.

    **Notable convenience methods:**

    * `qupdate(data)`: Initialize a update query for data
    * `qfilter()`: Initialize a filter query upto WHERE clasue.
    * `get(pkval)`: Get an item by primary key.

    Args:
        db (DB): DB object
        model_class (ModelType): model
    """
    def __init__(self, db: DB, model_class: ModelType = None):
        self.reset()
        self.db = db
        self.model = model_class # can be None
        def func(k):
            return Q(model_class._check_field_name_(k))
        self._f = _FieldNames(func) # no reset

    def __repr__(self):
        return f'ModelQuery({self.db}, {self.model})'

    def reset(self) -> 'ModelQuery':
        """Reset the model query by returning it to its initial state.

        Returns:
            self (Enables method chaining)
        """
        self._query_str_queue: List[str] = []
        self.end_query_str = ''
        self.start_query_str = ''
        self._args: List[Any] = []
        self._arg_count = 0
        self._named_args: Dict[str, Any] = {}
        self._named_args_mapper: Dict[str, int] = {}
        self.__filter_initiated = False
        self._ordering = ''
        self.__update_initiated = False
        return self


    @property
    def c(self) -> int:
        """Current available argument position in the query

        arg_count + 1 i.e if $1 and $2 has been used so far, then
        self.c is 3 so that you can use it to make $3.

        Returns:
            int
        """
        return self._arg_count + 1

    @property
    def db_table(self) -> str:
        """Table name of the model (quoted)
        """
        return Q(self.model._get_db_table_()) #type: ignore

    @property
    def pk(self) -> str:
        """Primary key name (quoted)
        """
        return Q(self.model._get_pk_()) #type: ignore

    @property
    def ordering(self) -> str:
        """Ordering query in SQL, does not include `ORDER BY`.

        Example: `"price" ASC, "quantity" DESC`
        """
        if not self._ordering:
            self._ordering = ','.join([' '.join(y) for y in self.model._get_ordering_(quote='"')]) # type: ignore
        return self._ordering

    @property
    def f(self) -> _FieldNames:
        """Field name container where names are quoted.

        It can be used to avoid spelling mistakes in writing query.

        Example: query `'select "profesion" from "table_name"'`

        will only produce error after actually running the query against
        a correctly spelled column 'profession'.

        while,

        query `f'select {self.f.profesion} from {self.db_table}'`

        will throw python exception telling you that there is no
        misspelled 'profesion' field.

        Note: you have to change `self` in above to the current
        `ModelQuery` instance
        """
        return self._f

    def _process_positional_args(self, *args):
        if args:
            self._args.extend(args)
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
                    self._args.append(v)
                    self._arg_count += 1
                    self._named_args_mapper[k] = self._arg_count
        return q

    def q(self, q: str, *args: Any) -> 'ModelQuery':
        """Add raw query stub without parsing to check for keyword arguments

        Use `$1`, `$2` etc. for arguments.

        Use `self.c` (instance property, use fstring) to get the current
        available argument position.

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
            *args (Any): positional arguments

        Returns:
            ModelQuery: self, enables method chaining.
        """
        self._process_positional_args(*args)
        self._query_str_queue.append(q)
        return self


    def q_(self, q: str, *args, **kwargs) -> 'ModelQuery':
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

    def qq(self, word: str) -> 'ModelQuery':
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


    def qc(self, word: str, rest: str, *args) -> 'ModelQuery':
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
            *args (any): args

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.qq(word).q(rest, *args)


    def qc_(self, word: str, rest: str, *args, **kwargs) -> 'ModelQuery':
        """Add query by quoting `word` while adding the `rest` as is.

        Same as `qc()` except this method parses the `rest` query string
        for keyword params in the format: `:field_name`

        Args:
            word (str): left part of query that needs to be quoted
            rest (str): right part of query that does not need to be quoted
            *args (any): args
            *kwargs: keyword args

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.qq(word).q_(rest, *args, **kwargs)

    def qorder(self):
        """Add ORDER BY

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.q('ORDER BY')

    def qo(self, order: str) -> 'ModelQuery':
        """Convert `+/-field_name,` to proper order_by criteria and add to query.

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

    def qu(self, data: dict) -> 'ModelQuery':
        """Convert data to `"column"=$n` query with args as the
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

    def qreturning(self, *column_names) -> 'ModelQuery':
        """Convenience to add a `RETURNING` clause.

        Args:
            column_names: column names.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        q = '","'.join(column_names)
        if q:
            q = f'RETURNING "{q}"'
        return self.q(q)

    def qwhere(self) -> 'ModelQuery':
        """Convenience to add 'WHERE' to the main query.

        Make use of `qc()` method to add conditions.

        Returns:
            ModelQuery: returns `self` to enable method chaining
        """
        return self.q('WHERE')

    def qfilter(self, no_ordering=False) -> 'ModelQuery':
        """Initiate a filter.

        This initiates a `SELECT` query upto `WHERE`. You can then use the
        `q()`, `qc()`, etc. methods to add conditions and finally
        execute the `fetch()` method to get all results or execute the
        `fetchrow()` method to get a single row.

        Example:

        ```python
        .qfilter().q('"price" >= $1 AND "status" = $2', 32.12, 'OK')
        ```

        Args:
            no_ordering (bool): Whether to remove the default ordering SQL. Defaults to False.

        Returns:
            ModelQuery: returns self to enable method chaining
        """
        if not self.__filter_initiated:
            down_fields = ','.join([Q(x) for x in self.model._get_fields_(up=False)]) #type: ignore
            self.reset().q(f'SELECT {down_fields} FROM "{self.model._get_db_table_()}" WHERE') #type: ignore
            self.__filter_initiated = True
            order_by = self.ordering
            if order_by and not no_ordering:
                self.end_query_str = f'ORDER BY {order_by}'
        else:
            raise ValueError(f"Filter is already initiated for this {self.__class__.__name__} query object: {self}")
        return self

    def qupdate(self, data: dict) -> 'ModelQuery':
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
            self.reset().q(f'UPDATE {self.db_table} SET').qu(data).qwhere()
            self.__update_initiated = True
        else:
            raise ValueError(f"update is already initiated for this {self.__class__.__name__} query: {self}")
        return self


    def getq(self) -> Tuple[str, List[Any]]:
        """Return query string and arg list

        Returns:
            tuple: (str, list) : (query, args)
        """
        query = ' '.join(self._query_str_queue)
        self._query_str_queue = [query]
        query = f'{self.start_query_str} {query} {self.end_query_str}'
        return query, self._args

    async def fetch(self, timeout: float = None) -> Union[List[ModelBase], List[Record]]:
        """Run query method `fetch` that returns the results in model class objects

        Returns the results in model class objects.

        Args:
            timeout (float, optional): Timeout in seconds. Defaults to None.

        Returns:
            List[Model]: List of model instances.
        """
        query, args = self.getq()
        return await self.db.fetch(query, *args, timeout=timeout, model_class=self.model)

    async def fetchrow(self, timeout: float = None) -> Union[ModelBase, Record]:
        """Make a query and get the first row.

        Resultant record is mapped to model_class object.

        Args:
            timeout (float, optional): Timeout value. Defaults to None.

        Returns:
            model_clas object or None if no rows were selected.
        """
        query, args = self.getq()
        return await self.db.fetchrow(query, *args, timeout=timeout, model_class=self.model)

    async def fetchval(self, column: int = 0, timeout: float = None) -> Any:
        """Run the query and return a column value in the first row.

        Args:
            column (int, optional): Column index. Defaults to 0.
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            Any: Coulmn (indentified by index) value of first row.
        """
        query, args = self.getq()
        return await self.db.fetchval(query, *args, column=column, timeout=timeout)

    async def execute(self, timeout: float = None) -> str:
        """Execute the query.

        Args:
            timeout (float, optional): Timeout. Defaults to None.

        Returns:
            str: Status of the last SQL command
        """
        query, args = self.getq()
        return await self.db.execute(query, *args, timeout=timeout)

    async def get(self, *vals: Any, col: str = '', comp: str = '=$1') -> Union[ModelBase, Record]:
        """Get the first row found by column and value.

        If `col` is not given, it defaults to the primary key (`pk`) of
        the model.

        If comparison is not given, it defaults to `=$1`

        Example:

        ```python
        from morm.db import DB

        db = DB(DB_POOL) # get a db handle.

        # get by pk:
        user5 = await db(User).get(5)

        # price between 5 and 2000
        user = await db(User).get(5, 2000, col='price', comp='BETWEEN $1 AND $2')
        ```

        Args:
            *vals (any): Values to compare. Must be referenced with $1, $2 etc.. in `comp`.
            col (str, optional): Column name. Defaults to the primary key.
            comp (str, optional): Comparison. Defaults to '=$1'.

        Returns:
            model_clas object or None if no rows were selected.
        """
        if not col:
            col = self.model.Meta.pk    #type: ignore
        return await self.reset().qfilter().qc(col, comp, *vals).fetchrow()

SERIALIZABLE = 'serializable'
REPEATABLE_READ = 'repeatable_read'
READ_COMMITTED = 'read_committed'

class Transaction():
    """Start a transaction.

    Example:

    ```python
    from morm.db import Transaction

    async with Transaction(DB_POOL) as tdb:
        # use tdb just like you use db
        user6 = await tdb(User).get(6)
        user6.age = 34
        await tdb.save(user6)
        user5 = await tdb(User).get(5)
        user5.age = 34
        await tdb.save(user6)
    ```

    Args:
        pool (Pool): Pool instance.
        isolation (str, optional): Transaction isolation mode, can be one of:
            'serializable',
            'repeatable_read',
            'read_committed'.
            Defaults to 'read_committed'.
            See https://www.postgresql.org/docs/9.5/transaction-iso.html
        readonly (bool, optional): Specifies whether this transaction is read-only. Defaults to False.
        deferrable (bool, optional): Specifies whether this transaction is deferrable. Defaults to False.
    """
    def __init__(self, pool: Pool, *,
                isolation: str=READ_COMMITTED,
                readonly: bool=False,
                deferrable: bool=False):
        self._pool = pool
        self.db = DB(None) # type: ignore
        self.tr = None
        self.tr_args = {
            'isolation': isolation,
            'readonly': readonly,
            'deferrable': deferrable,
        }

    async def __aenter__(self) -> DB:
        return await self.start()

    async def start(self) -> DB:
        """Start transaction.

        Raises:
            exceptions.TransactionError: When same object is used simultaneously for transaction

        Returns:
            DB: DB object.
        """
        if self.db._con:
            raise exceptions.TransactionError('Another transaction is running (or not ended properly) with this Transaction object')
        self.db._con = await self._pool.pool.acquire() # type: ignore
        self.tr = self.db._con.transaction(**self.tr_args) # type: ignore
        await self.tr.start() # type: ignore
        return self.db

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
                await self._pool.pool.release(self.db._con)
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
