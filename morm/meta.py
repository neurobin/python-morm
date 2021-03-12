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
    """Skeleton class for metadata

    Available meta settings:

    * `db_table` (*str*): db table name,
    * `abstract` (*bool*): Whether it is an abstract model. Abstract models do not have db table and are used as base models.
    * `pk` (*str*):  Primary key. Defaults to 'id',
    * `proxy` (*bool*): Whether it is a proxy model. Defaults to False. Proxy models inherit everything. This is only to have different pythonic behavior of a model. Proxy models can not define new fields and they do not have separate db table but share the same db table as their parents. Proxy setting is always inherited by child model, thus If you want to turn a child model non-proxy, set the proxy setting in its Meta class.
    * `ordering` (*Tuple[str]*): Ordering. Example: `('name', '-price')`, where name is ascending and price is in descending order.
    * `fields_up` (*Tuple[str]*): These fields only will be taken to update or save data onto db. Empty tuple means no restriction.
    * `fields_down` (*Tuple[str]*): These fields only will be taken to select/retrieve data from db. Empty tuple means no restriction.
    * `exclude_fields_up` (*Tuple[str]*): Exclude these fields when updating data to db. Empty tuple means no restriction.
    * `exclude_fields_down` (*Tuple[str]*): Exclude these fields when retrieving data from db. Empty tuple means no restriction.
    * `exclude_values_up` (*Dict[str, Tuple[Any]]*): Exclude fields with these values when updating. Empty dict and empty tuple means no restriction. Example: `{'': (None,), 'price': (0,)}` when field name is left empty ('') that criteria will be applied to all fields.
    * `exclude_values_down` (*Dict[str, Tuple[Any]]*): Exclude fields with these values when retrieving data. Empty dict and empty tuple means no restriction. Example: `{'': (None,), 'price': (0,)}` when field name is left empty ('') that criteria will be applied to all fields.
    * `f`: Access field names.
    """
    # _field_defs_ = {} This must not be included in Meta class
    # If it is included here, Meta class will inherently be allowed to pass
    # this/these fields which is not expected.

    # f is a reserved attribute to access field names
    def __init__(self):
        raise NotImplementedError("Creating instances of Meta class is not supported")
