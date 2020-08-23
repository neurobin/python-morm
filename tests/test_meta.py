import logging
import unittest

import morm.meta as mt


LOGGER_NAME = 'morm-test-field-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_Meta(self):
        with self.assertRaises(NotImplementedError):
            mta = mt.Meta()



if __name__ == "__main__":
    unittest.main(verbosity=2)
