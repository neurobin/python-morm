#!/usr/bin/python

from morm.migration import migration_manager
from .settings import DB_POOL                       # change accordingly
from morm import ModelPostgresql, Field

class SiteUser(ModelPostgresql):
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
