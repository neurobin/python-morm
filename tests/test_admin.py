import logging
import unittest
import os, sys
from morm.admin import main


LOGGER_NAME = 'morm-test-admin-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_main(self):
        tmpdir = '/tmp/morm_test_main'
        os.makedirs(tmpdir, exist_ok=True)
        os.chdir(tmpdir)
        sys.argv = [__file__, 'init']
        files = main()
        for file in files:
            path = os.path.join(tmpdir, file)
            print(f' - [x] Check if {path} content matches default {file} content')
            with open(path, 'r', encoding='utf-8') as f:
                self.assertEqual(files[file], f.read())


        print(f' - [x] Invalid command produces ValueError')
        sys.argv = [__file__, 'int']
        with self.assertRaises(ValueError):
            main()




if __name__ == "__main__":
    unittest.main(verbosity=2)
