"""Contains the Model's base Meta class
"""

__author__ = 'Md Jahidul Hamid <jahidulhamid@yahoo.com>'
__copyright__ = 'Copyright © Md Jahidul Hamid <https://github.com/neurobin/>'
__license__ = '[BSD](http://www.opensource.org/licenses/bsd-license.php)'
__version__ = '0.0.1'






class MetaType(type):
    def __setattr__(self, k, v):
        raise NotImplementedError("Meta class attribute can not be set outside of class definition.")
    def __delattr__(self, k):
        raise NotImplementedError("Meta class attribute can not be deleted outside of class definition.")


class Meta(metaclass=MetaType):
    # _field_defs_ = {} This must not be included in Meta class
    # If it is included here, Meta class will inherently be allowed to pass
    # this/these fields which is not expected.

    # f is a reserved attribute to access field names
    def __init__(self):
        raise NotImplementedError("Creating instances of Meta class is not supported")
