import logging
import unittest

from morm.q import QueryBuilder as QB


LOGGER_NAME = 'morm-test-field-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_QB(self):
        qb = QB()
        qb.R('from $1', 'test').L('select $2','*').R('where age=:age and profession=":profession"', age=23, profession='Teacher')
        q, args = qb.get_query()
        print(q)
        print(args)



if __name__ == "__main__":
    unittest.main(verbosity=2)
