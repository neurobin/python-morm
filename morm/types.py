"""Custom types.
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.1.1'


class SingletonMeta(type):
    """A metaclass to make singleton classes that can have only one
    instance.
    """
    _instances: dict = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args,
                                                                     **kwargs)
        return cls._instances[cls]


class VoidType(object, metaclass=SingletonMeta):
    """A custom type that represents false.

    For instances of this class, `len()` returns `0`, items and
    attributes can not be set.

    It's mainly used inside the containing package for null or
    non-existent value. `None` is a python object that is commonly used
    and should be retained its meaning as a valid value to a variable
    while we use `Void` internally to represent variables without any
    valid value.

    Thus, an object with `Void` value should be treated as an object
    with non-existent value.
    """

    def __new__(cls):
        return Void

    def __reduce__(self):
        return (VoidType, ())

    def __copy__(self):
        return Void

    def __deepcopy__(self, memo):
        return Void

    def __bool__(self):
        return False

    def __len__(self):
        return 0

    def __setitem__(self, key, value):
        raise NotImplementedError(self.__class__.__name__
                                 + " does not support setting items")

    def __setattr__(self, key, value):
        raise NotImplementedError(self.__class__.__name__
                                 + " does not support setting attributes")

    def __repr__(self):
        return 'Void'

# this one needs to be defined here.
Void = object.__new__(VoidType)
'''Used internally to represent non-existent value, thus `None` retains its usual meaning.'''
