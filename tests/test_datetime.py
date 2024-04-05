import logging
import unittest
import os, sys
import tempfile
import shutil
from morm import dt


LOGGER_NAME = 'morm-test-admin-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_main(self):
        print(dt.timestamp())
        print(dt.timestampu())




if __name__ == "__main__":
    unittest.main(verbosity=2)
