"""Common fields.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import re
from morm.fields.field import Field
from morm.model import ModelType, ModelBase


class ForeignKey(Field):
    """Foreign key field.

    Args:
        model (ModelType): model class.
        on_delete (str, optional): Either SET DEFAULT, SET NULL, RESTRICT, CASCADE or NO ACTION. Defaults to 'CASCADE'.
        kwargs : See morm.fields.Field for details.
    """
    def __init__(self, model: ModelType, on_delete='CASCADE', **kwargs):
        fk_pk = model.Meta.pk
        fk_type = model.Meta._field_defs_[fk_pk].sql_type
        fk_table = model.Meta.db_table
        alter_q = 'ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {constraint};ALTER TABLE {table} ADD CONSTRAINT {constraint} FOREIGN KEY ({column}) REFERENCES ' + f'"{fk_table}"("{fk_pk}")'
        if on_delete:
            alter_q += f' ON DELETE {on_delete}'
        alter_q += ';'
        super(ForeignKey, self).__init__(fk_type, **kwargs)
        pt = self.sql_conf.conf['sql_alter']
        self.sql_conf.conf['sql_alter'] = (alter_q, *pt)


class EmailField(Field):
    """Email field.

    Args:
        max_length (int, optional): Defaults to 255.
    """
    EMAIL_VALIDATION_REGEX = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')

    def __init__(self, max_length=255, **kwargs):
        sql_type = f'varchar({max_length})'
        super(EmailField, self).__init__(sql_type, validator=self.validate_email, **kwargs)

    def validate_email(self, email):
        return bool(self.EMAIL_VALIDATION_REGEX.fullmatch(email))
