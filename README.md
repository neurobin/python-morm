[![Build status image](https://travis-ci.org/neurobin/python-morm.svg?branch=release)](https://travis-ci.com/github/neurobin/python-morm) [![Coverage Status](https://coveralls.io/repos/github/neurobin/python-morm/badge.svg?branch=release)](https://coveralls.io/github/neurobin/python-morm?branch=release)

A minimal asynchronous database object relational mapper that supports transaction, connection pool and migration.

Currently supports *PostgreSQL* with `asyncpg`.

# Install

**Requires Python 3.7+**

```bash
pip install --user morm
```

# Init project

**Run `morm_admin init` in your project directory to make some default files such as `_morm_config_.py`, `mgr.py`**

Edit *_morm_config_.py* to put the correct database credentials:

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

# Model

It's more than a good practice to define a Base model first:

```python
from morm.model import Model
from morm.datetime import timestampz

class Base(Model):
    class Meta:
        pk = 'id' # setting primary key, it is defaulted to 'id'
        abstract = True

    # postgresql example
    id = Field('SERIAL', sql_onadd='NOT NULL')
    created_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', sql_alter=('SET DEFAULT NOW()',))
    updated_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', value=timestampz)

# Or you can inherit Base (with id field)
# or BaseCommon (with id, created_at, and updated_at fields)
# from morm.pg_models.
```

Then a minimal model could look like this:

```python
class User(Base):
    name = Field('varchar(65)')
    email = Field('varchar(255)')
    password = Field('varchar(255)')
```

An advanced model could look like:

```python
import random

def get_rand():
    return random.randint(1, 9)

class User(Base):
    class Meta:
        db_table = 'myapp_user'
        abstract = False    # default is False
        proxy = False       # default is False
        # ... etc...
        # see morm.meta.Meta for supported meta attributes.

    name = Field('varchar(65)')
    email = Field('varchar(255)')
    password = Field('varchar(255)')
    profession = Field('varchar(255)', default='Unknown')
    random = Field('integer', default=get_rand) # function can be default
```

## Initialize a model instance

keyword arguments initialize corresponding fields according to
the keys.

Positional arguments must be dictionaries of
keys and values.

Example:

```python
User(name='John Doe', profession='Teacher')
User({'name': 'John Doe', 'profession': 'Teacher'})
User({'name': 'John Doe', 'profession': 'Teacher'}, age=34)
```

## Special Model Meta attribute `f`:

You can access field names from `ModelClass.Meta.f`.

This allows a spell-safe way to write the field names. If you
misspell the name, you will get `AttributeError`.

```python
f = User.Meta.f
my_data = {
    f.name: 'John Doe',         # safe from spelling mistake
    f.profession: 'Teacher',    # safe from spelling mistake
    'hobby': 'Gardenning',      # unsafe from spelling mistake
}
```

## Model Meta attributes


* `db_table` (*str*): db table name,
* `abstract` (*bool*): Whether it is an abstract model. Abstract models do not have db table and are used as base models.
* `pk` (*str*):  Primary key. Defaults to 'id',
* `proxy` (*bool*): Whether it is a proxy model. Defaults to False. Proxy models inherit everything. This is only to have different pythonic behavior of a model. Proxy models can not define new fields and they do not have separate db table but share the same db table as their parents. Proxy setting is always inherited by child model, thus If you want to turn a child model non-proxy, set the proxy setting in its Meta class.
* `ordering` (*Tuple[str]*): Ordering. Example: `('name', '-price')`, where name is ascending and price is in descending order.
* `fields_up` (*Tuple[str]*): These fields only will be taken to update or save data onto db. Empty tuple means no restriction.
* `fields_down` (*Tuple[str]*): These fields only will be taken to select/retrieve data from db. Empty tuple means no restriction.
* `exclude_fields_up` (*Tuple[str]*): Exclude these fields when updating data to db. Empty tuple means no restriction.
* `exclude_fields_down` (*Tuple[str]*): Exclude these fields when retrieving data from db. Empty tuple means no restriction.
* `exclude_values_up` (*Dict[str, Tuple[Any]]*): Exclude fields with these values when updating. Empty dict and empty tuple means no restriction. Example: `{'': (None,), 'price': (0,)}` when field name is left empty ('') that criteria will be applied to all fields.
* `exclude_values_down` (*Dict[str, Tuple[Any]]*): Exclude fields with these values when retrieving data. Empty dict and empty tuple means no restriction. Example: `{'': (None,), 'price': (0,)}` when field name is left empty ('') that criteria will be applied to all fields.
* `f`: Access field names.

# CRUD

All available database operations are exposed through `DB` object.

Example:

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

# Create
user = User(name='John Doe', profession='Teacher')
await db.save(user)

# Read
user5 = await db(User).get(5)

# Update
user5.age = 30
await db.save(user5)

# Delete
await db.delete(user5)
```

# Query

Calling `db(Model)` gives you a model query handler which have several query methods to help you make queries.

Use `.q(query, *args)` method to make queries with positional arguments. If you want named arguments, use the uderscored version of these methods. For example, `q(query, *args)` has an underscored version `q_(query, *args, **kwargs)` that can take named arguments.

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
user_list = await qh.fetch()
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

## Filter

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

f = User.Meta.f
user_list = await db(User).qfilter().q(f'"{f.profession}"=$1', 'Teacher').fetch()
user_list = await db(User).qfilter().qc(f.profession, '=$1', 'Teacher').fetch()
```

It is safer to use `${qh.c}` instead of `$1`, `${qh.c+1}` instead of `$2`, etc..

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

qh = db(User)
user_list = await qh.qfilter()\
                    .q(f'{qh.f.profession} = ${qh.c} AND {qh.f.age} = ${qh.c+1}', 'Teacher', 30)\
                    .fetch()
```

## Get

The get method has the signature `get(*vals, col='', comp='=$1')`.

It gets the first row found by column and value. If `col` is not given, it defaults to the primary key (`pk`) of the model. If comparison is not given, it defaults to `=$1`

Example:

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

# get by pk:
user5 = await db(User).get(5)

# price between 5 and 2000
user = await db(User).get(5, 2000, col='price', comp='BETWEEN $1 AND $2')
```


# Transaction

```python
from morm.db import Transaction

async with Transaction(DB_POOL) as tdb:
    # use tdb just like you use db
    user6 = await tdb(User).get(6)
    user6.age = 34
    await tdb.save(user6)
    user5 = await tdb(User).get(5)
    user5.age = 34
    await tdb.save(user5)
```

# Migration

You should have created the *_morm_config_.py* and *mgr.py* file with `morm_admin init`.

List all the models that you want migration for in *mgr.py*. You will know how to edit it once you open it.

Then, to make migration files, run:

```bash
python mgr.py makemigrations
```

This will ask you for confirmation on each changes, add `-y` flag to bypass this.

run

```bash
python mgr.py migrate
```

to apply the migrations.


## Adding data into migration

Go into migration directory after making the migration files and look for the `.py` files inside `queue` directory. Identify current migration files, open them for edit. You will find something similar to this:

```python
import morm

class MigrationRunner(morm.migration.MigrationRunner):
    """Run migration with pre and after steps.
    """
    migration_query = """{migration_query}"""

    # async def run_before(self):
    #     """Run before migration

    #     self.tdb is the db handle (transaction)
    #     self.model is the model class
    #     """
    #     dbm = self.tdb(self.model)
    #     # # Example
    #     # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
    #     # await dbm.execute()
    #     # # etc..

    # async def run_after(self):
    #     """Run after migration.

    #     self.tdb is the db handle (transaction)
    #     self.model is the model class
    #     """
    #     dbm = self.tdb(self.model)
    #     # # Example
    #     # dbm.q('SOME QUERY TO SET "column_1"=$1', 'some_value')
    #     # await dbm.execute()
    #     # # etc..
```

As you can see, there are `run_before` and `run_after` hooks. You can use them to make custom queries before and after the migration query. You can even modify the migration query itself.

Example:

```python
...
    async def run_before(self):
        """Run before migration

        self.tdb is the db handle (transaction)
        self.model is the model class
        """
        user0 = self.model(name='John Doe', profession='Engineer', age=45)
        await self.tdb.save(user0)
...
```
