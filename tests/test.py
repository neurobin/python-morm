import asyncio
import logging
import unittest

from morm.db import Pool, DB


LOGGER_NAME = 'morm-'
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

from morm import Model, Field

class User(Model):
    _db_ = DB(SNORM_DB_POOL)
    name = Field('varchar(255)')
    profession = Field('varchar(255)')

class BigUser(User):
    age = Field("int")


class test_table(User):pass



class TestMethods(unittest.TestCase):

    async def _test_default(self):
        db = DB(SNORM_DB_POOL)
        dbpool = await db.pool()
        await dbpool.execute('CREATE TABLE IF NOT EXISTS "BigUser" (id SERIAL not null PRIMARY KEY, name varchar(255), profession varchar(255), age int)')
        # await db.execute('INSERT into test_table')
        mos = await test_table._get_(where='name like $1 order by id asc', prepared_args=['%dumm%'])
        print(mos.__dict__)
        # # print(mos[0].__dict__)
        # print(BigUser()._fields_)
        # print(BigUser._get_table_name_())
        # b = BigUser()
        # b.name = 'jahid'
        # b.age = 28
        # print(b._get_insert_query_())
        # id = await b._insert_()
        # print(id)

        # b1 = await BigUser._get_(where='id=1')
        # b1.name = 'Jahidul Hamid'
        # print(b1._get_update_query_())
        # await b1._update_()
        # b = BigUser()
        # b.name = 'John Doeee'
        # b.profession = 'Teacher'
        # await b._save_()
        # b.age = 34
        # await b._save_()
        d = {
            'name': 'John Doe',
            'age': 45,
        }
        b = BigUser(d)
        await b._save_()

    def test_default(self):
        asyncio.get_event_loop().run_until_complete(self._test_default())

if __name__ == "__main__":
    unittest.main()
