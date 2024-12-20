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
        on_delete (str, optional): query to add with ON DELETE. Either SET DEFAULT, SET NULL, RESTRICT, CASCADE or NO ACTION.
        on_update (str, optional): query to add With ON UPDATE.
        deferrable (int, optional): 0,1, or 2. Defaults to 0.
            - 0: NOT DEFERRABLE (Default)
            - 1: DEFERRABLE INITIALLY IMMEDIATE:  check will be made immediately after each statement
            - 2: DEFERRABLE INITIALLY DEFERRED: check will be made after the transaction is complete
        kwargs : See morm.fields.Field for details.
    """
    def __init__(self, model: ModelType, on_delete='', on_update='', deferrable=0, **kwargs):
        fk_pk = model.Meta.pk
        fk_type = model.Meta._field_defs_[fk_pk].sql_type
        if fk_type.lower() == 'serial':
            fk_type = 'integer'
        elif fk_type.lower() == 'bigserial':
            fk_type = 'bigint'
        fk_table = model.Meta.db_table
        alter_q = 'ALTER TABLE "{table}" DROP CONSTRAINT IF EXISTS "__FK_{table}_{column}__";ALTER TABLE "{table}" ADD CONSTRAINT "__FK_{table}_{column}__" FOREIGN KEY ("{column}") REFERENCES "%s"("%s")' % (fk_table, fk_pk)
        if on_delete:
            alter_q += f' ON DELETE {on_delete}'
        if on_update:
            alter_q += f' ON UPDATE {on_update}'
        if deferrable == 1:
            alter_q += ' DEFERRABLE INITIALLY IMMEDIATE'
        elif deferrable == 2:
            alter_q += ' DEFERRABLE INITIALLY DEFERRED'
        alter_q += ';'
        super(ForeignKey, self).__init__(fk_type, **kwargs)
        pt = self.sql_conf.conf['sql_alter']
        self.sql_conf.conf['sql_alter'] = (alter_q, *pt)


class EmailField(Field):
    """Email field.

    Args:
        max_length (int, optional): Defaults to 255.
    """

    def __init__(self, max_length=255, allow_null=True, **kwargs):
        sql_type = f'varchar({max_length})'
        def validate_email(email):
            if not email: return True if allow_null else False
            EMAIL_VALIDATION_REGEX = re.compile(r'[^@\s]+@[^@\s]+\.[^@\s]+')
            return bool(EMAIL_VALIDATION_REGEX.fullmatch(email))
        super(EmailField, self).__init__(sql_type, validator=validate_email, **kwargs)
