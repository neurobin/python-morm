"""Common Postgresql Models.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


from morm.model import Model
from morm.fields import Field
from morm.datetime import timestampz


class Base(Model):
    """A model that defines default column 'id'
    """
    class Meta:
        abstract = True
    id = Field('SERIAL', sql_onadd='NOT NULL')


class BaseCommon(Model):
    """A model that defines default columns:

    id: Auto incremented integer
    created_at: timestampz
    update_at: timestampz (used with pythonic default)
    """
    class Meta:
        abstract = True
    id = Field('SERIAL', sql_onadd='NOT NULL')
    created_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', sql_alter=('SET DEFAULT NOW()',))
    updated_at = Field('TIMESTAMPZ', sql_onadd='NOT NULL', value=timestampz)
