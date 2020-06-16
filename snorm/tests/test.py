
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

class TestMethods(unittest.TestCase):

    def test_default(self):
        pass

if __name__ == "__main__":
    unittest.main()
