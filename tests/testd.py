
from pydantic import BaseModel
from pydantic.dataclasses import dataclass, Field
import typing




@dataclass
class Users():
    id: int = Field('id serial int primary key')
    name: str = Field('varchar(45)')

    class Config:
        orm_mode = True
