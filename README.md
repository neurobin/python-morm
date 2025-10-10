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
* `unique_groups` (*Dict[str, List[str]]*): Define multi-column unique constraints. Each key is a group name, and the value is a list of field names that form a composite unique constraint. The order of fields in the list is preserved in the database constraint. Example: `{'user_email': ['user_id', 'email'], 'category_order': ['category', 'order']}`.
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

# Indexing

You can use the `index: Tuple[str] | str | None` parameter to define what type/s of indexing should be applied to the field. Examples:

```python
class User(Base):
    parent_id = Field('integer', index='hash')
    username = Field('varchar(65)', index='hash,btree') # two indexes
    email = Field('varchar(255)', index=('hash', 'btree')) # tuple is allowed as well
    perms = Field('integer[]', index='gin:gin__int_ops')
```

If you want to remove the indexing, Add a `-` minus sign to the specific index and then run migration. After that you can safely remove the index keyword, e.g:

```bash
--- parent_id = Field('integer', index='-hash')
===$ ./mgr makemigrations
===$ ./mgr migrate
>>> parent_id = Field('integer', index='') # now you can remove the hash
```

# Field/Model grouping

You can group your model fields, for example, you can define groups like `admin`, `mod`, `staff`, `normal` and make your model fields organized into these groups. This will enable you to implement complex field level organized access controls. You can say, that the `password` field belongs to the *admin* group, then `subscriptions` field to *mod* group and then `active_subscriptions` to *staff* group.

```python
class UserAdmin(Base):
    class Meta:
        groups = ('admin',) # this model belongs to the admin group
    password = Field('varchar(100)', groups=('admin',))
    subscriptions = Field('integer[]', groups=('mod',))
    active_subscriptions = Field('integer[]', groups=('staff',))
```

# Sudo (Elevated access to fields)

We believe writing to certain fields or areas of your system should require elevated access.

`Field` can take an argument `sudo` that means **elevated access required**. IF `sudo` is set to true for some field, you will not be able to write to this field using the `ModelQuery` (direct raw query can still be performed) unless your db instance is set to have `sudo=True` as well:

```python
db = DB(DB_POOL, sudo=True)
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

# Advanced Developer Guide

## Understanding the Architecture

### Core Components

**morm** is built around several key modules that work together:

1. **Model Layer** (`morm.model`): Metaclass-based model system with field definitions
2. **Database Layer** (`morm.db`): Connection pooling, transactions, and query execution
3. **Query Builder** (`morm.q`, `ModelQuery`): Fluent API for building SQL queries
4. **Field System** (`morm.fields`): Type-safe field definitions with validation
5. **Migration System** (`morm.migration`): Forward-only schema migrations

### Model Metaclass System

The ORM uses Python metaclasses to provide powerful model introspection and validation:

```python
from morm.model import Model
from morm.fields import Field

class User(Model):
    # Fields are discovered and processed at class creation time
    # The ModelType metaclass handles:
    # - Field name assignment
    # - Inheritance resolution (abstract, proxy models)
    # - Meta attribute processing
    # - Validation setup

    name = Field('varchar(100)')
    email = Field('varchar(255)')
```

**Key metaclass features:**

- **Field Discovery**: All `Field` instances are automatically detected and registered
- **Meta Inheritance**: Smart inheritance of Meta attributes based on abstract/proxy settings
- **Validation**: Field names starting with `_` are rejected (reserved for internal use)
- **Type Safety**: `Meta.f` provides spell-safe field name access

## Advanced Query Building

### Query Counter (`qh.c`)

The query counter is essential for building dynamic queries safely:

```python
from morm.db import DB

db = DB(DB_POOL)
qh = db(User)

# Instead of hardcoding $1, $2, use the counter
query = qh.q(f'SELECT * FROM {qh.db_table}')\
          .q(f'WHERE {qh.f.age} > ${qh.c}', 18)\
          .q(f'AND {qh.f.status} = ${qh.c}', 'active')\
          .q(f'AND {qh.f.created_at} > ${qh.c}', '2024-01-01')
```

**Why use `qh.c`?**
- Prevents parameter numbering errors
- Makes queries composable and reusable
- Automatically tracks positional argument count

### Named Parameters

For complex queries, use named parameters:

```python
qh = db(User)\
    .q_(f'SELECT * FROM {qh.db_table}')\
    .q_(f'WHERE {qh.f.age} > :min_age AND {qh.f.status} = :status',
        min_age=18, status='active')
```

### Query Method Families

**Positional arguments** (`q`, `qc`, `qu`):
- Fast, no parsing overhead
- Use when you don't need named params

**Named arguments** (`q_`, `qc_`):
- Adds parsing overhead
- Use for readability and reusability

```python
# Efficient for simple queries
qh.qc('status', '=$1', 'active')

# Better for complex, reusable queries
qh.qc_('status', '=:status', status='active')
```

## Field System Deep Dive

### Field Types and SQL Mapping

```python
from morm.fields import Field

class Product(Base):
    # String types
    name = Field('varchar(255)')
    description = Field('text')

    # Numeric types
    price = Field('numeric(10,2)')  # or use max_digits/decimal_places
    quantity = Field('integer')
    rating = Field('real')

    # Boolean
    active = Field('boolean')

    # Date/Time
    created = Field('timestamp with time zone')

    # Arrays (PostgreSQL)
    tags = Field('varchar(50)[]')  # or use array_dimension
    prices = Field('numeric', array_dimension=(10,))  # Array with dimension

    # JSON
    metadata = Field('jsonb')
```

### Field Parameters Deep Dive

```python
class User(Base):
    # Basic constraints
    email = Field('varchar(255)',
                  unique=True,           # Adds UNIQUE constraint
                  sql_onadd='NOT NULL')  # Applied when column is added

    # Indexing strategies
    username = Field('varchar(65)',
                     index='btree,hash')  # Multiple indexes
    tags = Field('integer[]',
                 index='gin:gin__int_ops')  # GIN with operator class

    # Default values
    status = Field('varchar(20)',
                   default='pending')    # Static default
    created = Field('timestamp',
                    default=datetime.now)  # Callable default

    # Perpetual values (always recomputed)
    updated = Field('timestamp',
                    value=datetime.now)  # Always set on save

    # Validation
    age = Field('integer',
                validator=lambda x: x is None or (0 <= x <= 150),
                validator_text='Age must be between 0 and 150')

    # Sudo (elevated access required)
    salary = Field('numeric(10,2)',
                   sudo=True)  # Requires db = DB(pool, sudo=True)

    # Field groups
    ssn = Field('varchar(11)',
                groups=('admin', 'hr'))

    # Allow null
    middle_name = Field('varchar(100)',
                        allow_null=True)
```

### Multi-Column Unique Constraints

You can define composite unique constraints using the `unique_groups` Meta attribute. This is useful when you need uniqueness across multiple columns rather than just a single column.

```python
class UserEmail(Base):
    class Meta:
        # Define groups of fields that must be unique together
        unique_groups = {
            'user_email': ['user_id', 'email'],  # (user_id, email) must be unique
            'user_provider': ['user_id', 'provider']  # (user_id, provider) must be unique
        }

    user_id = Field('integer')
    email = Field('varchar(255)')
    provider = Field('varchar(50)')
    verified = Field('boolean', default=False)

class ProductSKU(Base):
    class Meta:
        unique_groups = {
            'warehouse_sku': ['warehouse_id', 'sku'],  # Unique SKU per warehouse
        }

    warehouse_id = Field('integer')
    sku = Field('varchar(100)')
    quantity = Field('integer')
```

**Important notes:**
- Each key in `unique_groups` is a group name (used in constraint naming)
- The value is a list of field names that form the composite unique constraint
- The order of fields in the list matters and is preserved in the database constraint
- The migration system automatically detects changes to unique_groups and generates appropriate SQL

**Constraint naming:** Constraints are named using the pattern `__UNQ_{table}_{groupname}__`

Example:
```python
# For the UserEmail model above, the constraint would be named:
# __UNQ_UserEmail_user_email__
# __UNQ_UserEmail_user_provider__
```

**Real-world use cases:**

1. **User authentication with multiple providers:**
   ```python
   class UserAuth(Base):
       class Meta:
           unique_groups = {
               'user_provider': ['user_id', 'provider'],
           }

       user_id = Field('integer')
       provider = Field('varchar(50)')  # 'google', 'github', 'email'
       provider_user_id = Field('varchar(255)')
   ```

2. **Multi-tenant applications:**
   ```python
   class TenantData(Base):
       class Meta:
           unique_groups = {
               'tenant_key': ['tenant_id', 'key'],
           }

       tenant_id = Field('integer')
       key = Field('varchar(100)')
       value = Field('text')
   ```

3. **Inventory management:**
   ```python
   class Inventory(Base):
       class Meta:
           unique_groups = {
               'location_product': ['location_id', 'product_id'],
           }

       location_id = Field('integer')
       product_id = Field('integer')
       quantity = Field('integer')
   ```

4. **Ordering/sorting with categories:**
   ```python
   class MenuItem(Base):
       class Meta:
           unique_groups = {
               'category_order': ['category_id', 'sort_order'],
           }

       category_id = Field('integer')
       sort_order = Field('integer')
       name = Field('varchar(255)')
   ```

### Field Validation Flow

When you set a field value, it goes through this flow:

```
1. __setattr__ called
2. Field validator checked (if fails, raises ValueError)
3. FieldValue.set_value() called
4. Field.clean() runs validator -> modifier -> validator
5. Value stored in FieldValue._value
6. value_change_count incremented
```

When saving to database:

```
1. get_insert_query() or get_update_query() called
2. _get_FieldValue_data_valid_() filters fields
3. _clean_{fieldname}() method called for each field (if defined)
4. Field sudo permissions checked
5. Query built with cleaned values
```

## Meta Attribute Reference

### Field Control

```python
class User(Base):
    class Meta:
        # Include/Exclude fields for retrieval (SELECT)
        fields_down = ('id', 'name', 'email')  # Only these fields
        exclude_fields_down = ('password',)     # All except these

        # Include/Exclude fields for updates (INSERT/UPDATE)
        fields_up = ()                          # Empty = all allowed
        exclude_fields_up = ('id', 'created')   # Don't allow these
```

**Priority**: `fields_*` takes precedence over `exclude_fields_*`

### Value Filtering

```python
from morm.void import Void

class User(Base):
    class Meta:
        # Exclude specific values from retrieval
        exclude_values_down = {
            '': (None, Void),           # Exclude None/Void for all fields
            'status': ('deleted',),     # Exclude 'deleted' status
        }

        # Exclude specific values from updates
        exclude_values_up = {
            '': (None,),                # Don't update with None
            'price': (0,),              # Don't allow 0 price
        }
```

### Model Behavior

```python
class User(Base):
    class Meta:
        db_table = 'app_users'         # Custom table name
        abstract = True                 # No table, used as base
        proxy = False                   # Default: False
        pk = 'id'                       # Primary key field name
        ordering = ('name', '-created') # + = ASC, - = DESC
        sudo = True                     # All fields require elevated access
        groups = ('admin',)             # Model belongs to groups
        ignore_init_exclude_error = True  # Allow excluded fields in __init__
```

## Advanced Patterns

### Abstract Base Models

Create reusable base models with common fields:

```python
from morm.model import Model
from morm.fields import Field
from morm.dt import timestamp

class TimestampedModel(Model):
    class Meta:
        abstract = True

    created_at = Field('timestamp with time zone',
                       sql_alter=('ALTER TABLE "{table}" ALTER COLUMN "{column}" SET DEFAULT NOW()',))
    updated_at = Field('timestamp with time zone',
                       value=timestamp)

class AuditModel(TimestampedModel):
    class Meta:
        abstract = True

    created_by = Field('integer')
    updated_by = Field('integer')

# Concrete model with all fields from both base classes
class Article(AuditModel):
    title = Field('varchar(255)')
    content = Field('text')
```

### Proxy Models

Proxy models share the same table but have different Python behavior:

```python
class User(Base):
    name = Field('varchar(100)')
    email = Field('varchar(255)')
    role = Field('varchar(20)')

class AdminUser(User):
    class Meta:
        proxy = True  # No new table
        exclude_fields_down = ()  # Show all fields for admins

class PublicUser(User):
    class Meta:
        proxy = True
        exclude_fields_down = ('email', 'role')  # Hide sensitive fields
```

**Important**: Proxy models:
- Cannot define new fields
- Share the same database table
- Can have different `fields_down`, `exclude_fields_down`, etc.
- Proxy setting is inherited by child models

### Lifecycle Hooks

Override these async methods to add custom behavior:

```python
class User(Base):
    async def _pre_save_(self, db):
        """Called before save (both insert and update)"""
        # Validate business rules
        if not self.email:
            raise ValueError("Email required")

    async def _post_save_(self, db):
        """Called after save"""
        # Send welcome email, log activity, etc.
        await send_notification(self.email)

    async def _pre_insert_(self, db):
        """Called before insert only"""
        # Set initial values
        self.status = 'pending'

    async def _post_insert_(self, db):
        """Called after insert"""
        # Create related records
        profile = UserProfile(user_id=self.id)
        await db.save(profile)

    async def _pre_update_(self, db):
        """Called before update only"""
        pass

    async def _post_update_(self, db):
        """Called after update"""
        pass

    async def _pre_delete_(self, db):
        """Called before delete"""
        # Check constraints
        if self.role == 'admin':
            raise ValueError("Cannot delete admin users")

    async def _post_delete_(self, db):
        """Called after delete"""
        # Cleanup related data
        await db(UserProfile).qfilter().qc('user_id', '=$1', self.id).execute()
```

### Complex Queries

#### Joins (Manual)

```python
db = DB(DB_POOL)
qh = db(User)

# Manual joins are supported
query = qh.q(f'''
    SELECT u.*, p.bio
    FROM {qh.db_table} u
    LEFT JOIN "user_profile" p ON u.id = p.user_id
    WHERE u.{qh.f.status} = ${qh.c}
''', 'active')

# Returns User instances with only User fields populated
users = await query.fetch()

# For custom results, use fetch without model_class
results = await query.fetch(model_class=None)  # Returns Record objects
```

#### Aggregations

```python
# Count users by role
qh = db(User)
result = await qh.q(f'''
    SELECT {qh.f.role}, COUNT(*) as count
    FROM {qh.db_table}
    GROUP BY {qh.f.role}
''').fetch(model_class=None)

for row in result:
    print(f"{row['role']}: {row['count']}")
```

#### Subqueries

```python
qh = db(User)
subquery = f'''(
    SELECT user_id
    FROM "orders"
    WHERE total > 1000
)'''

users = await qh.q(f'''
    SELECT * FROM {qh.db_table}
    WHERE id IN {subquery}
''').fetch()
```

### Transaction Best Practices

```python
from morm.db import Transaction, SERIALIZABLE

# Standard transaction
async with Transaction(DB_POOL) as tdb:
    user = await tdb(User).get(1)
    user.balance -= 100
    await tdb.save(user)

    order = Order(user_id=user.id, amount=100)
    await tdb.save(order)
    # Automatically commits on success, rolls back on exception

# With isolation level
async with Transaction(DB_POOL, isolation=SERIALIZABLE) as tdb:
    # Highest isolation level
    pass

# Read-only transaction (optimization)
async with Transaction(DB_POOL, readonly=True) as tdb:
    users = await tdb(User).qfilter().qc('status', '=$1', 'active').fetch()

# Manual transaction control
tr = Transaction(DB_POOL)
tdb = await tr.start()
try:
    # Your operations
    await tr.commit()
except:
    await tr.rollback()
    raise
finally:
    await tr.end()
```

### Efficient Bulk Operations

```python
db = DB(DB_POOL)

# Bulk insert using raw query
users_data = [
    ('John', 'john@example.com'),
    ('Jane', 'jane@example.com'),
    # ... more users
]

qh = db(User)
await qh.q(f'''
    INSERT INTO {qh.db_table} ({qh.f.name}, {qh.f.email})
    VALUES ($1, $2), ($3, $4)
''', *[item for sublist in users_data for item in sublist]).execute()

# Or use unnest for PostgreSQL
await qh.q(f'''
    INSERT INTO {qh.db_table} ({qh.f.name}, {qh.f.email})
    SELECT * FROM UNNEST($1::varchar[], $2::varchar[])
''', [u[0] for u in users_data], [u[1] for u in users_data]).execute()
```

### Using Field Groups for Access Control

```python
class User(Base):
    class Meta:
        groups = ('public',)

    name = Field('varchar(100)', groups=('public',))
    email = Field('varchar(255)', groups=('member',))
    phone = Field('varchar(20)', groups=('member', 'admin'))
    salary = Field('numeric', groups=('admin',))
    ssn = Field('varchar(11)', groups=('admin',))

# Check field groups
admin_fields = User._group_fields_('admin')  # ('phone', 'salary', 'ssn')
member_fields = User._group_fields_('member')  # ('email', 'phone')

# Check if field belongs to group
is_admin_field = User._check_group_('admin', 'salary')  # True
```

### Migration Workflow

```python
# In your mgr.py after running `morm_admin init`

from _morm_config_ import DB_POOL
from morm.migration import migration_manager
from app.models import User, Product, Order  # Your models

if __name__ == '__main__':
    migration_manager(
        pool=DB_POOL,
        base_path='./migration_data',
        models=[User, Product, Order]
    )
```

**Migration commands:**

```bash
# Create migration files
python mgr.py makemigrations

# Apply migrations
python mgr.py migrate

# Delete migrations (useful during development)
python mgr.py delete_migration_files 5 10  # Delete migrations 5-10

# Auto-confirm (CI/CD)
python mgr.py makemigrations -y
python mgr.py migrate -y
```

### Custom Migration Logic

```python
# In migration_data/User/.queue/User_00000042_*.py

import morm

class MigrationRunner(morm.migration.MigrationRunner):
    migration_query = """ALTER TABLE "User" ADD COLUMN "status" varchar(20);"""

    async def run_before(self):
        """Runs before the migration query"""
        # Backup data, validate preconditions, etc.
        count = await self.tdb.fetchval('SELECT COUNT(*) FROM "User"')
        if count > 10000:
            print(f"Warning: Migrating {count} users")

    async def run_after(self):
        """Runs after the migration query"""
        # Set default status for existing users
        dbm = self.tdb(self.model)
        await dbm.q('UPDATE "User" SET "status" = $1 WHERE "status" IS NULL',
                   'active').execute()
```

## Performance Tips

1. **Use connection pooling** appropriately:
   ```python
   # Adjust pool size based on your workload
   DB_POOL = Pool(
       min_size=10,   # Keep some connections ready
       max_size=90,   # Limit concurrent connections
       max_queries=50000,  # Recycle connections periodically
   )
   ```

2. **Limit fields in SELECT**:
   ```python
   # Only fetch needed fields
   users = await db(User).qfilter(select_cols=['id', 'name']).fetch()
   ```

3. **Use `fields_down` in Meta** for frequently accessed models:
   ```python
   class UserList(User):
       class Meta:
           proxy = True
           fields_down = ('id', 'name', 'avatar')  # Only essential fields
   ```

4. **Batch operations** when possible:
   ```python
   # Instead of multiple single saves
   async with Transaction(DB_POOL) as tdb:
       for user_data in users:
           user = User(user_data)
           await tdb.save(user)
   ```

5. **Use indexes** wisely:
   ```python
   # Add indexes for frequently queried columns
   email = Field('varchar(255)', index='btree')
   tags = Field('integer[]', index='gin')
   ```

## Debugging Tips

### Enable Query Logging

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('morm.db').setLevel(logging.DEBUG)
```

### Inspect Generated Queries

```python
qh = db(User)
query, args = qh.qfilter().qc('status', '=$1', 'active').getq()
print(f"Query: {query}")
print(f"Args: {args}")
```

### Check Field Definitions

```python
# Get all fields with their config
fields_json = User._get_all_fields_json_()
print(fields_json)

# Get specific field
field = User._get_all_fields_()['email']
print(field.sql_conf.to_json())
```

### Validate Model Setup

```python
# Check what fields will be retrieved
down_fields = list(User._get_fields_(up=False))
print(f"Fields for retrieval: {down_fields}")

# Check what fields can be updated
up_fields = list(User._get_fields_(up=True))
print(f"Fields for update: {up_fields}")

# Check sudo fields
sudo_fields = list(User._sudo_fields_())
print(f"Sudo fields: {sudo_fields}")
```

## Common Pitfalls

1. **Mutable defaults**: Don't use mutable defaults directly
   ```python
   # WRONG
   tags = Field('jsonb', default=[])

   # CORRECT
   tags = Field('jsonb', default=lambda: [])
   ```

2. **In-place mutations**: Don't modify mutable values in-place
   ```python
   # WRONG - change won't be tracked
   user.tags.append('new-tag')
   await db.save(user)

   # CORRECT - assign new value
   user.tags = [*user.tags, 'new-tag']
   await db.save(user)
   ```

3. **Field name typos**: Use `Meta.f` to prevent typos
   ```python
   # Typo won't be caught
   data = {'profesion': 'Teacher'}  # typo!

   # Typo will raise AttributeError
   f = User.Meta.f
   data = {f.profession: 'Teacher'}  # spell-safe
   ```

4. **Forgetting await**: All database operations are async
   ```python
   # WRONG
   user = db(User).get(1)  # Returns coroutine

   # CORRECT
   user = await db(User).get(1)
   ```

5. **Transaction context**: Don't mix db and tdb
   ```python
   # WRONG
   async with Transaction(DB_POOL) as tdb:
       user = await db(User).get(1)  # Using wrong handle

   # CORRECT
   async with Transaction(DB_POOL) as tdb:
       user = await tdb(User).get(1)  # Use tdb inside transaction
   ```
