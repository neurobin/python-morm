"""Common utils.

"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import importlib.util
import sys, os, re
from importlib import import_module as importlib_import_module

def Open(path: str, mode: str, **kwargs):
    """Wrapper for open with utf-8 encoding

    Args:
        path (str): path to file
        mode (str): file open mode

    Returns:
        open: open context manager handle
    """
    return open(path, mode, encoding='utf-8', **kwargs)

def loaded_module(dotted_path: str):
    """Return module if the module is loaded, otherwise return None

    Args:
        dotted_path (str): module dotted_path

    Returns:
        module if loaded, None otherwise
    """
    # Check whether module is loaded and fully initialized.
    if not (
        (module := sys.modules.get(dotted_path))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ): return None
    return module

def import_from_path(dotted_path: str, path: str):
    """Import a module from path and record it in sys.modules[dotted_path]

    Args:
        dotted_path (str): module dotted_path
        path (str): path (file path)

    Returns:
        object: module object
    """
    if not (module := loaded_module(dotted_path)):
        spec = importlib.util.spec_from_file_location(dotted_path, path)
        module = importlib.util.module_from_spec(spec) # type: ignore
        sys.modules[dotted_path] = module
        spec.loader.exec_module(module) # type: ignore
    return module

def import_module(path, base_path=None):
    """Import a module by string path.

    Args:
        path (str): path to module, can be a dotted path as well
        base_path (str, optional): base path (file path only) from where it can be imported by absolute import. Defaults to None.

    Returns:
        module: imported module
    """
    absolute_unix_path = None
    if path[0] == os.path.sep and not base_path:
            absolute_unix_path = path
    if os.path.sep in path:
        path = path.replace(base_path, '') if base_path else path
        path = re.sub(r'\.py$', '', path)
        path = path.replace(os.path.sep, '.').strip('.')
    if absolute_unix_path:
        return import_from_path(path, absolute_unix_path)

    if not (module := loaded_module(path)):
        module = importlib_import_module(path)
    return module

def import_object(path, object_name=None, base_path=None):
    """Import an object by string path.

    Args:
        path (str): path to object, can be a dotted path as well
        object_name (str, optional): name of the object to import. Defaults to last part of dotted path.
        base_path (str, optional): base path from where it can be imported by absolute import. Defaults to None.

    Returns:
        object: imported object
    """
    if not object_name:
        try:
            path, object_name = path.rsplit(".", 1)
        except ValueError as err:
            raise ImportError("%s doesn't look like an object path, please pass object_name parameter" % path) from err

    try:
        return getattr(import_module(path, base_path=base_path), object_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (path, object_name)
        ) from err
