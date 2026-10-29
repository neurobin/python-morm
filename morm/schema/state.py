"""Plain, comparable representation of a database schema.
"""

from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional, List


@dataclass(frozen=True)
class Column:
    name: str
    type: str                   # format_type() output, e.g. 'character varying(212)'
    notnull: bool
    default: Optional[str]      # pg_get_expr() output or None
    identity: str = ''          # attidentity: '', 'a' (always), 'd' (by default)
    generated: str = ''         # attgenerated: '' or 's' (stored)
    position: int = 0           # attnum, evidence only, never compared

    def same_def(self, other: 'Column') -> bool:
        return (self.type, self.notnull, self.default, self.identity, self.generated) == \
               (other.type, other.notnull, other.default, other.identity, other.generated)


@dataclass(frozen=True)
class Constraint:
    name: str
    kind: str                   # 'p' primary, 'u' unique, 'f' foreign key, 'c' check, 'x' exclusion
    definition: str             # pg_get_constraintdef() output
    columns: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Index:
    name: str
    definition: str             # normalized: CREATE [UNIQUE] INDEX "name" ON "table" USING ...
    columns: Tuple[str, ...] = ()


@dataclass
class Table:
    name: str
    columns: Dict[str, Column] = field(default_factory=dict)
    constraints: Dict[str, Constraint] = field(default_factory=dict)
    indexes: Dict[str, Index] = field(default_factory=dict)

    def column_list(self) -> List[Column]:
        return sorted(self.columns.values(), key=lambda c: c.position)


@dataclass
class SchemaState:
    tables: Dict[str, Table] = field(default_factory=dict)

    def subset(self, names) -> 'SchemaState':
        return SchemaState({k: v for k, v in self.tables.items() if k in names})


def differences(a: SchemaState, b: SchemaState) -> List[str]:
    """Human readable list of differences between two states (empty if equal).

    Column positions are ignored.
    """
    out: List[str] = []
    for t in sorted(set(a.tables) | set(b.tables)):
        ta, tb = a.tables.get(t), b.tables.get(t)
        if ta is None:
            out.append(f'table {t}: missing on the left')
            continue
        if tb is None:
            out.append(f'table {t}: missing on the right')
            continue
        for c in sorted(set(ta.columns) | set(tb.columns)):
            ca, cb = ta.columns.get(c), tb.columns.get(c)
            if ca is None or cb is None:
                out.append(f'column {t}.{c}: missing on the {"left" if ca is None else "right"}')
            elif not ca.same_def(cb):
                out.append(f'column {t}.{c}: {_coldesc(ca)} != {_coldesc(cb)}')
        for kind, da, db in (('constraint', ta.constraints, tb.constraints), ('index', ta.indexes, tb.indexes)):
            for n in sorted(set(da) | set(db)):
                xa, xb = da.get(n), db.get(n)
                if xa is None or xb is None:
                    out.append(f'{kind} {t}.{n}: missing on the {"left" if xa is None else "right"}')
                elif xa.definition != xb.definition:
                    out.append(f'{kind} {t}.{n}: {xa.definition} != {xb.definition}')
    return out


def _coldesc(c: Column) -> str:
    s = c.type + (' NOT NULL' if c.notnull else ' NULL')
    if c.default is not None:
        s += f' DEFAULT {c.default}'
    if c.identity:
        s += f' IDENTITY({c.identity})'
    if c.generated:
        s += ' GENERATED'
    return s
