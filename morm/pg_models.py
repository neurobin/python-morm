

from morm.model import Model
from morm.fields import Field
from morm.datetime import timestampz


class Base(Model):
    """A model that defines default columns (postgresql): id
    """
    class Meta:
        abstract = True
    id = Field('SERIAL', sql_onadd='NOT NULL')


class BaseCommon(Model):
    """A model that defines default columns (postgresql):

    id: Auto incremented integer
    created_at: timestampz
    update_at: timestampz (used with pythonic default)
    and updated_at
    """
    class Meta:
        abstract = True
    id = Field('SERIAL', sql_onadd='NOT NULL')
    created_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', sql_alter=('SET DEFAULT NOW()',))
    updated_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', value=timestampz)
