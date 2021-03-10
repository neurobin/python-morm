import logging
import unittest

from morm.q import Q


LOGGER_NAME = 'morm-test-q-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_Q(self):
        self.assertEqual(Q('string'), '"string"')



if __name__ == "__main__":
    unittest.main(verbosity=2)
