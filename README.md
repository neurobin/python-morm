[![Build status image](https://travis-ci.org/neurobin/python-morm.svg?branch=release)](https://travis-ci.com/github/neurobin/python-morm) [![Coverage Status](https://coveralls.io/repos/github/neurobin/python-morm/badge.svg?branch=release)](https://coveralls.io/github/neurobin/python-morm?branch=release)

Minimal database object relational mapper.

Currently supports *PostgreSQL* with `asyncpg`.

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
```

Then a minimal model could look like this:

```python
class User(Base):
    name = Field('varchar(65)')
    email = Field('varchar(255)')
    password = Field('varchar(16)')
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
    password = Field('varchar(16)')
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
User({'name': 'John Doe', 'profession': 'Teacher', 'active': True}, age=34)
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
