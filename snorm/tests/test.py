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
    pass

class TestMethods(unittest.TestCase):

    async def _test_default(self):
        db = DB(SNORM_DB_POOL)
        await db.execute('CREATE TABLE IF NOT EXISTS test_table (id SERIAL not null PRIMARY KEY, name varchar(255))')
        # await db.execute('INSERT into test_table')

    def test_default(self):
        asyncio.get_event_loop().run_until_complete(self._test_default())

if __name__ == "__main__":
    unittest.main()
