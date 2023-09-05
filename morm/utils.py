"""Common utils.

"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'


import importlib.util
import sys, os, re
from importlib import import_module as system_import_module

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
        name (str): module name (should be dotted path)
        path (str): path (file path)

    Returns:
        object: module object
    """
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec) # type: ignore
    spec.loader.exec_module(module) # type: ignore
    return module

def _cached_import(module_name):
    print(module_name)
    # Check whether module is loaded and fully initialized.
    if not (
        (module := sys.modules.get(module_name))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ):
        module = system_import_module(module_name)
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
    return _cached_import(path)

def import_object(path, object_name=None, base_path=None):
    """Import an object by string path.

    Args:
        path (str): path to object, can be a dotted path as well
        object_name (str, optional): name of the object to import. Defaults to None.
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
        return getattr(import_module(path, base_path), object_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (path, object_name)
        ) from err
