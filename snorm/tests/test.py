import asyncio
import asyncpg
import logging
import unittest


LOGGER_NAME = 'dborm-'
log = logging.getLogger(LOGGER_NAME)

def get_file_content(path):
    cont = ''
    try:
        with open(path, 'r') as f:
            cont = f.read();
    except Exception as e:
        log.exception("E: could not read file: " + path)
    return cont

class DB(object):
    def __init__(self, dsn, username, password, min_size=10, max_size=100):
        self._pool = None
        self.dsn = dsn
        self.username = username
        self.password = password
        self.min_size = min_size
        self.max_size = max_size

    @property
    async def pool(self):
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.dsn,
                                                  user=self.username,
                                                  password=self.password,
                                                  min_size=self.min_size,
                                                  max_size=self.max_size)
        return self._pool

    async def close(self):
        if self._pool:
            await self._pool.close()


class TestMethods(unittest.TestCase):

    def test_default(self):
        pass

if __name__ == "__main__":
    unittest.main()
