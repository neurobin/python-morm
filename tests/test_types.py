
import unittest
from copy import copy, deepcopy
import pickle

from morm.types import Void, VoidType


class TestMethods(unittest.TestCase):
    def test_Void(self):
        self.assertTrue(Void is VoidType())
        self.assertTrue(len(Void) == 0)
        self.assertTrue(bool(Void) == False)
        self.assertTrue(Void is copy(Void))
        self.assertTrue(Void is deepcopy(Void))
        self.assertTrue(Void is VoidType())
        with self.assertRaises(NotImplementedError):
            Void.fdsfds = 9
        with self.assertRaises(NotImplementedError):
            Void['fds'] = 9

        s = pickle.dumps(Void)
        v = pickle.loads(s)
        self.assertTrue(v is Void)


if __name__ == "__main__":
    unittest.main(verbosity=2)
