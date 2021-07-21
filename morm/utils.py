"""Common utils.

"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import importlib.util

def Open(path: str, mode: str, **kwargs):
    """Wrapper for open with utf-8 encoding

    Args:
        path (str): path to file
        mode (str): file open mode

    Returns:
        open: open context manager handle
    """
    return open(path, mode, encoding='utf-8', **kwargs)

def import_from_path(name: str, path: str):
    """Import a module from path

    Args:
        name (str): module name
        path (str): path

    Returns:
        object: module object
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec) # type: ignore
    spec.loader.exec_module(module) # type: ignore
    return module
