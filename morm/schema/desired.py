"""Desired schema: the models created in a throwaway shadow schema.

The models' own SQL (``sql_type``, ``sql_onadd``, ``sql_alter``,
``Meta.unique_groups``, ``Meta.indexes``) is executed in a fresh schema that is
first on ``search_path``, then the schema is read back with the same catalog
queries as the real one.  The caller's transaction must be rolled back
afterwards.
"""

import uuid
from typing import Dict, List, Tuple, Sequence

import re

from morm.model import ModelType
from morm.fields.field import get_composite_index_create_sql, normalize_meta_indexes
from morm.schema.state import SchemaState
from morm.schema.introspect import introspect


_REF_RE = re.compile(r'REFERENCES\s+(?:"((?:[^"]|"")+)"|([^\s("]+))', re.I)


class ModelSQLError(Exception):
    pass


def model_sql(model: ModelType) -> Tuple[str, List[str]]:
    """CREATE TABLE statement and the follow-up statements for a model."""
    table = model._get_db_table_()
    cols = []
    alters = []
    for name, f in model._get_persisted_fields_().items():
        create_q, alter_q = f.sql_conf.get_query_column_create_stub(table)
        cols.append(f'    {create_q}')
        if alter_q:
            alters.append(alter_q)
    for group, field_list in dict(model.Meta.unique_groups).items():
        columns = ', '.join(f'"{c}"' for c in field_list)
        alters.append(f'ALTER TABLE "{table}" ADD CONSTRAINT "__UNQ_{table}_{group}__" UNIQUE ({columns});')
    for iname, spec in normalize_meta_indexes(model.Meta.indexes).items():
        alters.append(get_composite_index_create_sql(table, iname, spec['cols'], spec['indexes']))
    create = f'CREATE TABLE "{table}" (\n' + ',\n'.join(cols) + '\n);'
    return create, alters


def check_models(models: Sequence[ModelType]) -> Dict[str, ModelType]:
    out: Dict[str, ModelType] = {}
    for m in models:
        if m._is_abstract_() or m._is_proxy_():
            raise ModelSQLError(f'{m.__name__}: abstract and proxy models can not be migrated')
        t = m._get_db_table_()
        if t in out:
            raise ModelSQLError(f'{m.__name__} and {out[t].__name__} both use table "{t}"')
        out[t] = m
    return out


async def build_desired(con, models: Sequence[ModelType], base_schema: str = 'public') -> SchemaState:
    """Create the models in a shadow schema and introspect it.

    Must run inside a transaction that the caller rolls back.
    """
    bytable = check_models(models)
    shadow = f'_morm_shadow_{uuid.uuid4().hex[:12]}'
    await con.execute(f'CREATE SCHEMA "{shadow}"')
    path = f'"{shadow}", "{base_schema}"' + (', "public"' if base_schema != 'public' else '')
    await con.execute("SELECT set_config('search_path', $1, true)", path)

    # Inline references (sql_onadd REFERENCES ...) need the referenced table
    # first, otherwise the name would resolve to the real table in the base
    # schema.
    sqls = {t: model_sql(m) for t, m in bytable.items()}
    order: List[str] = []
    state_: Dict[str, int] = {}

    def visit(t: str, chain: Tuple[str, ...]):
        if state_.get(t) == 2:
            return
        if state_.get(t) == 1:
            raise ModelSQLError('Circular inline REFERENCES between tables: ' + ' -> '.join(chain + (t,))
                                + '; move one of them to sql_alter (ADD CONSTRAINT ... FOREIGN KEY)')
        state_[t] = 1
        for ref in _REF_RE.findall(sqls[t][0]):
            r = ref[0] or ref[1]
            if r in bytable and r != t:
                visit(r, chain + (t,))
        state_[t] = 2
        order.append(t)

    for t in bytable:
        visit(t, ())

    creates = [(bytable[t].__name__, sqls[t][0]) for t in order]
    alters = [(bytable[t].__name__, q) for t in order for q in sqls[t][1]]
    for kind, stmts in (('CREATE TABLE', creates), ('', alters)):
        if not stmts:
            continue
        try:  # one round trip; statement by statement only to locate an error
            async with con.transaction():
                await con.execute('\n'.join(q for _, q in stmts))
            continue
        except Exception:
            pass
        for name, q in stmts:
            try:
                await con.execute(q)
            except Exception as e:
                raise ModelSQLError(f'{name}: {kind + " failed: " if kind else ""}{e}\n{q}') from e

    leaked = await con.fetch('''
        SELECT c.conname, src.relname AS src, dst.relname AS dst FROM pg_constraint c
        JOIN pg_class src ON src.oid = c.conrelid JOIN pg_class dst ON dst.oid = c.confrelid
        WHERE c.contype = 'f' AND src.relnamespace = $1::regnamespace
          AND dst.relnamespace <> $1::regnamespace''', shadow)
    for r in leaked:
        if r['dst'] in bytable:
            raise ModelSQLError(f'{r["src"]}.{r["conname"]} references the real "{r["dst"]}" instead of the '
                                'model table; reference it by its plain table name')
    state = await introspect(con, shadow, search_path=path)
    await con.execute("SELECT set_config('search_path', $1, true)", f'"{base_schema}"')
    return state
