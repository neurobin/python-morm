"""Read a schema from the Postgres catalog.

The same queries are used for the real schema and for the shadow schema, so
Postgres itself normalizes types, defaults, constraint and index definitions on
both sides.  ``search_path`` is set to the inspected schema while reading so
that names come out unqualified.
"""

import re
from typing import Iterable

from morm.schema.state import Column, Constraint, Index, Table, SchemaState
from morm.schema import LEDGER_TABLE


_Q_TABLES = '''
SELECT c.oid, c.relname FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = $1 AND c.relkind IN ('r', 'p')
ORDER BY c.relname
'''

_Q_COLUMNS = '''
SELECT a.attrelid, a.attname, format_type(a.atttypid, a.atttypmod) AS type,
       a.attnotnull, pg_get_expr(d.adbin, d.adrelid) AS default,
       a.attidentity::text AS identity, a.attgenerated::text AS generated, a.attnum
FROM pg_attribute a
LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
WHERE a.attrelid = ANY($1::oid[]) AND a.attnum > 0 AND NOT a.attisdropped
'''

# contype 'n' (NOT NULL constraints, Postgres 18+) is covered by attnotnull.
_Q_CONSTRAINTS = '''
SELECT c.conrelid, c.conname, c.contype::text AS kind, pg_get_constraintdef(c.oid) AS def,
       ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY k(n, i)
             JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.n
             ORDER BY k.i)::text[] AS cols
FROM pg_constraint c
WHERE c.conrelid = ANY($1::oid[]) AND c.contype IN ('p', 'u', 'f', 'c', 'x')
ORDER BY c.conname
'''

# Indexes that back a constraint are part of the constraint.
_Q_INDEXES = '''
SELECT i.indrelid, ic.relname, pg_get_indexdef(i.indexrelid) AS def,
       ARRAY(SELECT a.attname FROM unnest(i.indkey::int2[]) k(n)
             JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.n)::text[] AS cols
FROM pg_index i
JOIN pg_class ic ON ic.oid = i.indexrelid
WHERE i.indrelid = ANY($1::oid[])
  AND NOT EXISTS (SELECT 1 FROM pg_constraint c
                  WHERE c.conindid = i.indexrelid AND c.conrelid = i.indrelid
                    AND c.contype IN ('p', 'u', 'x'))
ORDER BY ic.relname
'''

_INDEX_ON = re.compile(r'^(CREATE (?:UNIQUE )?INDEX )(\S+)( ON (?:ONLY )?)(\S+)( .*)$', re.S)


def _unqualify(name: str, schema: str) -> str:
    for p in (f'"{schema}".', f'{schema}.'):
        if name.startswith(p):
            return name[len(p):]
    return name


def _quote(name: str) -> str:
    if name.startswith('"'):
        return name
    return '"' + name.replace('"', '""') + '"'


def normalize_indexdef(defn: str, schema: str) -> str:
    """CREATE INDEX x ON public.t USING ... -> CREATE INDEX "x" ON "t" USING ..."""
    m = _INDEX_ON.match(defn)
    if not m:
        return defn
    head, iname, on, tname, rest = m.groups()
    return f'{head}{_quote(iname)}{on}{_quote(_unqualify(tname, schema))}{rest}'


async def introspect(con, schema: str = 'public', search_path: str = '',
                     exclude: Iterable[str] = (LEDGER_TABLE,)) -> SchemaState:
    """Read tables, columns, constraints and indexes of ``schema``.

    Must be called inside a transaction (search_path is set locally).
    """
    if not search_path:
        search_path = _quote(schema) + (', "public"' if schema != 'public' else '')
    await con.execute("SELECT set_config('search_path', $1, true)", search_path)
    exclude = set(exclude)
    state = SchemaState()
    byoid = {}
    for r in await con.fetch(_Q_TABLES, schema):
        if r['relname'] in exclude:
            continue
        t = Table(r['relname'])
        state.tables[t.name] = t
        byoid[r['oid']] = t
    oids = list(byoid)
    if not oids:
        return state
    for r in await con.fetch(_Q_COLUMNS, oids):
        byoid[r['attrelid']].columns[r['attname']] = Column(
            name=r['attname'], type=r['type'], notnull=r['attnotnull'], default=r['default'],
            identity=r['identity'] or '', generated=r['generated'] or '', position=r['attnum'])
    for r in await con.fetch(_Q_CONSTRAINTS, oids):
        byoid[r['conrelid']].constraints[r['conname']] = Constraint(
            name=r['conname'], kind=r['kind'], definition=r['def'], columns=tuple(r['cols']))
    for r in await con.fetch(_Q_INDEXES, oids):
        byoid[r['indrelid']].indexes[r['relname']] = Index(
            name=r['relname'], definition=normalize_indexdef(r['def'], schema), columns=tuple(r['cols']))
    return state
