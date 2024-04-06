[![Build status image](https://travis-ci.org/neurobin/python-morm.svg?branch=release)](https://travis-ci.com/github/neurobin/python-morm) [![Coverage Status](https://coveralls.io/repos/github/neurobin/python-morm/badge.svg?branch=release)](https://coveralls.io/github/neurobin/python-morm?branch=release)

A minimal asynchronous database object relational mapper that supports transaction, connection pool and migration.

Currently supports *PostgreSQL* with `asyncpg`.

# Install

**Requires Python 3.10+**

```bash
pip install morm
```

# Init project

**Run `morm_admin init -p app` in your project directory to make some default files such as `_morm_config_.py`, `mgr.py`**

Edit *_morm_config_.py* to put the correct database credentials:

```python
from morm.db import Pool

DB_POOL = Pool(
    dsn='postgres://',
    host='localhost',
    port=5432,
    user='user',
    password='pass',
    database='db_name',
    min_size=10,
    max_size=90,
)
```

This will create and open an asyncpg pool which will be automatically closed at exit.

# Model

It's more than a good practice to define a Base model first:

```python
from morm.pg_models import BaseCommon as Model

# BaseCommon defines id, created_at and updated_at fields.
# While pg_models.Base defines only id.

class Base(Model):
    class Meta:
        abstract = True
```

Then a minimal model could look like this:

```python
from morm.fields import Field

class User(Base):
    name = Field('varchar(65)')
    email = Field('varchar(255)')
    password = Field('varchar(255)')
```

Advanced models could look like this:

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

class UserProfile(User):
    class Meta:
        proxy = True
        exclude_fields_down = ('password',) # exclude sensitive fields in retrieval
        # this will also exclude this field from swagger docs if you are
        # using our fastAPI framework
```

## Rules for field names

1. Must not start with an underscore (`_`). You can set arbitrary variables to the model instance with names starting with underscores; normally you can not set any variable to a model instance. Names not starting with an underscore are all expected to be field names, variables or methods that are defined during class definition.
2. `_<name>_` such constructions are reserved for pre-defined overridable methods such as `_pre_save_`, `_post_save_`, etc..
3. Name `Meta` is reserved to be a class that contains configuration of the model for both model and model instance.


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

## Validations

You can setup validation directly on the attribute or define a class method named `_clean_fieldname` to run a validation and change the value before it is inserted or updated into the db. These two types of validations work a bit differently:

1. **Validation on field attribute:** Can not change the value, must return True or False. It has more strict behavior than the `_clean_*` method for the attribute. This will run even when you are setting the value of an attribute by model instance, e.g `user.islive = 'live'` this would throw `ValueError` if you set the validator as `islive = Field('boolean', validator=lambda x: x is None or isinstance(x, bool))`.
2. **Validation with `_clean_{fieldName}` method:** Can change the value and must return the final value. It is only applied during insert or update using the model query handler (using `save` or `update` or `insert`).

Example:

```python
class User(Base):
    class Meta:
        db_table = 'myapp_user'
        abstract = False    # default is False
        proxy = False       # default is False
        # ... etc...
        # see morm.meta.Meta for supported meta attributes.

    name = Field('varchar(65)')
    email = Field('varchar(255)')
    # restrict your devs to things such as user.password = '1234567' # <8 chars
    password = Field('varchar(255)', validator=lambda x: x is None or len(x)>=8)
    profession = Field('varchar(255)', default='Unknown')
    random = Field('integer', default=get_rand) # function can be default

    def _clean_password(self, v: str):
        if not v: return v # password can be empty (e.g for third party login)
        if len(v) < 8:
            raise ValueError(f"Password must be at least 8 characters long.")
        if len(v) > 100:
            raise ValueError(f"Password must be at most 100 characters long.")
        # password should contain at least one uppercase, one lowercase, one number, and one special character
        if not any(c.isupper() for c in v):
            raise ValueError(f"Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError(f"Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError(f"Password must contain at least one number.")
        if not any(c in '!@#$%^&*()-_=+[]{}|;:,.<>?/~' for c in v):
            raise ValueError(f"Password must contain at least one special character.")
        return v
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

## Filter

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

f = User.Meta.f
user_list = await db(User).qfilter().q(f'"{f.profession}"=$1', 'Teacher').fetch()
user_list = await db(User).qfilter().qc(f.profession, '=$1', 'Teacher').fetch()
```

It is safer to use `${qh.c}` instead of `$1`, `${qh.c+1}` instead of `$2`, etc.. :

```python
from morm.db import DB

db = DB(DB_POOL) # get a db handle.

qh = db(User)
user_list = await qh.qfilter()\
                    .q(f'{qh.f.profession} = ${qh.c} AND {qh.f.age} = ${qh.c+1}', 'Teacher', 30)\
                    .fetch()
```

# Query

Calling `db(Model)` gives you a model query handler which has several query methods to help you make queries.

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

**Migration is a new feature and only forward migrations are supported as of now.**

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
        user0 = self.model(name='John Doe', profession='Software Engineer', age=45)
        await self.tdb.save(user0)
...
```

# Do not do these

1. Do not delete migration files manually, use `python mgr.py delete_migration_files <start_index> <end_index>` command instead.
2. Do not modify mutable values in-place e.g `user.addresses.append('Some address')`, instead set the value: `user.addresses = [*user.addresses, 'Some address']` so that the `__setattr__` is called, on which `morm` depends for checking changed fields for the `db.save()` and related methods.

# Initialize a FastAPI project

Run `init_fap app` in your project root. It will create a directory structure like this:

```
├── app
│   ├── core
│   │   ├── __init__.py
│   │   ├── models
│   │   │   ├── base.py
│   │   │   ├── __init__.py
│   │   │   └── user.py
│   │   ├── schemas
│   │   │   └── __init__.py
│   │   └── settings.py
│   ├── __init__.py
│   ├── main.py
│   ├── tests
│   │   ├── __init__.py
│   │   └── v1
│   │       ├── __init__.py
│   │       └── test_sample.py
│   ├── v1
│   │   ├── dependencies
│   │   │   └── __init__.py
│   │   ├── __init__.py
│   │   ├── internal
│   │   │   └── __init__.py
│   │   └── routers
│   │       ├── __init__.py
│   │       └── root.py
│   └── workers.py
├── app.service
├── .gitignore
├── gunicorn.sh
├── mgr
├── mgr.py
├── _morm_config_.py
├── nginx
│   ├── app
│   └── default
├── requirements.txt
├── run
└── vact
```

You can run the dev app with `./run` or the production app with `./gunicorn.sh`.

To run the production app as a service with `systemctl start app`, copy the **app.service** to `/etc/systemd/system`

**Notes:**

* You can setup your venv path in the `vact` file. To activate the venv with all the environment vars, just run `. vact`.
* An environment file `.env_APP` is created in your home directory containing dev and production environments.


# Pydantic support

You can get pydantic model from any morm model using the `_pydantic_` method, e.g `User._pydantic_()` would give you the pydantic version of your `User` model. The `_pydantic_()` method supports a few parameters to customize the generated pydantic model:

* `up=False`: Defines if the model should be for up (update into database) or down (retrieval from database).
* `suffix=None`: You can add a suffix to the name of the generated pydantic model.
* `include_validators=None`: Whether the validators defined in each field (with validator parameter) should be added as pydantic validators. When `None` (which is default) validators will be included for data update into database (i.e for `up=True`). Note that, the model field validators return True or False, while pydantic validators return the value, this conversion is automatically added internally while generating the pydantic model.

If you are using our FastAPI framework, generating good docs for user data retrieval using the User model would be as simple as:

```python
@router.get('/crud/{model}', responses=Res.schema_all(User._pydantic_())
async def get(request: Request, model: str, vals = '', col: str='', comp: str='=$1'):
     if some_authentication_error:
        raise Res(status=Res.Status.unauthorized, errors=['Invalid Credentials!']) # throws a correct HTTP error with additional error message
    ...
    return Res(user)
```

The above will define all common response types: 200, 401, 403, etc.. and the 200 success response will show an example with correct data types from your User model and will show only the fields that are allowed to be shown (controlled with `exclude_fields_down` or `fields_down` in the `User.Meta`).


# JSON handling

It may seem tempting to add json and jsonb support with `asyncpg.Connection.set_type_codec()` method, but we have not provided any option to use this method easily in `morm`, as it turned out to be making the queries very very slow. If you want to handle json, better add a `_clean_{field}` method in your model and  do the conversion there:

```python
class User(Base):
    settings = Field('jsonb')
    ...

    def _clean_settings(self, v):
        if not isinstance(v, str):
            v = json.dumps(v)
        return v
```

If you want to have it converted to json during data retrieval from database as well, pass a validator which should return False if it is not json, and then pass a modifier in the field to do the conversion. Do note that modifier only runs if validator fails. Thus you will set and get the value as json (list or dict) and the `_clean_settings` will covert it back to text during database insert or update.

```python
class User(Base):
    settings = Field('jsonb', validator=lambda x: isinstance(x, list|dict), modifier=lambda x: json.loads(x))
    ...

    def _clean_settings(self, v):
        if not isinstance(v, str):
            v = json.dumps(v)
        return v
```
