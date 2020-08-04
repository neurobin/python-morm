
import typing
from collections import OrderedDict
import re




# from pydantic import BaseModel
# from pydantic.dataclasses import dataclass, Field

# @dataclass
# class Users():
#     id: int = Field('id serial int primary key')
#     name: str = Field('varchar(45)')

#     class Config:
#         orm_mode = True

s = """
        class BigUser(User):
            name = Field("int")
            age = Field("int");zaz = Field("int")
            zzz = Field("int")
            profession\
            = Field('varchar(255)')

            bnb = Field("int")


"""

_fields_ = {
    'age': 23,
    'bnb': 23,
    'name': 'fds',
    'profession': 'Teacher',
    'zaz': 34,
    'zzz': 234,
}

def get_match_index(k, v):
    m = re.search(f"(;|^)[\\s]*\\b{k}\\s*=", s, re.M)
    if m:
        return m.start()
    return 0

res = get_match_index('zaz', 34)
print(res)

# def get_ordered_fields(fields, cls_def):
#     new_fields = OrderedDict()
#     for k, v in
