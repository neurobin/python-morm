
import unittest

from morm.version import __version__

class TestMethods(unittest.TestCase):
    def test_version(self):
        self.assertTrue(isinstance(__version__, str))
        self.assertTrue(len(__version__.split('.')) >= 3)

if __name__ == "__main__":
    unittest.main(verbosity=2)
