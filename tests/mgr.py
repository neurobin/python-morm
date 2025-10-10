#!/usr/bin/python

from morm.migration import migration_manager
from settings import DB_POOL                       # change accordingly
from morm.fields import Field
from morm.pg_models import Base

class SiteUser(Base):
    class Meta:
        unique_groups = {
            'name_profession': ['name', 'profession'],
            'profession_age': ['profession', 'age']
        }

    name = Field('varchar(254)')
    profession = Field('varchar(258)')
    age = Field('integer')


MIGRATION_BASE_PATH = '/tmp/my_migration_base_path'      # change accordingly

migration_models = [
    SiteUser,                                      # change accordingly
]

if __name__ == '__main__':
    migration_manager(DB_POOL, MIGRATION_BASE_PATH, migration_models)
    DB_POOL.close()
