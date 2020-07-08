import asyncio
import logging
import unittest
from async_property import async_property, async_cached_property

from snorm.db import Pool, DB


LOGGER_NAME = 'snorm-'
log = logging.getLogger(LOGGER_NAME)

def get_file_content(path):
    cont = ''
    try:
        with open(path, 'r') as f:
            cont = f.read();
    except Exception as e:
        log.exception("E: could not read file: " + path)
    return cont


SNORM_DB_POOL = Pool(
    dsn='postgres://',
    host='localhost',
    port=5432,
    user='jahid',
    password='jahid',
    database='test',
    min_size=10,
    max_size=100,
)


class Model(object):
    _db_ = DB(SNORM_DB_POOL)
    _table_name_ = 'test_table' # debug


    @classmethod
    def _get_table_name_(cls):
        if hasattr(cls, '_table_name_'):
            return cls._table_name_
        return cls.__name__

    @classmethod
    def _get_dbi(cls):
        return cls._db_

    @classmethod
    async def _select(cls, what='*', where='true', prepared_args=None):
        """Make a select query for this model.

        Args:
            what (str, optional): Columns. Defaults to '*'.
            where (str, optional): Where conditon (sql). Defaults to 'true'.
            prepared_args (list, optional): prepared arguments. Defaults to None.

        Returns:
            list: List of model instances
        """
        if not prepared_args: prepared_args = []
        query = 'SELECT %s FROM %s WHERE %s' % (what, cls._get_table_name_(), where)
        return await cls._get_dbi().select(query, *prepared_args, model_class=cls)

    @classmethod
    async def _select_first(cls, what='*', where='true', prepared_args=None):
        """Make a select query to retrieve one item of from this model.

        'LIMIT 1' is added at the end of the query.

        Args:
            what (str, optional): Columns. Defaults to '*'.
            where (str, optional): Where condition. Defaults to 'true'.
            prepared_args (list, optional): prepared arguments. Defaults to None.

        Returns:
            Model: A model instance.
        """
        if not prepared_args: prepared_args = []
        query = 'SELECT %s FROM %s WHERE %s limit 1' % (what, cls._get_table_name_(), where)
        return await cls._get_dbi().select_first(query, *prepared_args, model_class=cls)



class TestMethods(unittest.TestCase):

    async def _test_default(self):
        db = DB(SNORM_DB_POOL)
        await db.execute('CREATE TABLE IF NOT EXISTS test_table (id SERIAL not null PRIMARY KEY, name varchar(255))')
        # await db.execute('INSERT into test_table')
        mos = await Model._select_first(where='name like $1 order by id asc', prepared_args=['%dumm%'])
        print(mos.__dict__)
        # print(mos[0].__dict__)

    def test_default(self):
        asyncio.get_event_loop().run_until_complete(self._test_default())

if __name__ == "__main__":
    unittest.main()
