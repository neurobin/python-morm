import logging
import unittest
import os, sys
import tempfile
import shutil
from morm.admin import main


LOGGER_NAME = 'morm-test-admin-'
log = logging.getLogger(LOGGER_NAME)



class TestMethods(unittest.TestCase):
    def test_main(self):
        tmpdir = tempfile.mkdtemp()
        os.chdir(tmpdir)
        sys.argv = [__file__, 'init']
        files = main()
        main() # touch FileExistsError
        for file in files:
            path = os.path.join(tmpdir, file)
            print(f' - [x] Check if {path} content matches default {file} content')
            with open(path, 'r', encoding='utf-8') as f:
                self.assertEqual(files[file], f.read())


        print(f' - [x] Invalid command produces ValueError')
        sys.argv = [__file__, 'int']
        with self.assertRaises(ValueError):
            main()

        shutil.rmtree(tmpdir)




if __name__ == "__main__":
    unittest.main(verbosity=2)
