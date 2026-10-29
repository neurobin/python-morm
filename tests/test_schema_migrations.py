"""Tests for catalog based migrations (morm.schema).

These tests DROP and recreate the ``public`` schema of the test database, so
they only run when pointed at a database explicitly:

    MORM_TEST_PGHOST=/path/to/socket MORM_TEST_PGPORT=55432 MORM_TEST_PGUSER=morm \
    MORM_TEST_PGDATABASE=morm_test MORM_TEST_ALLOW_RESET=1 \
    python -m unittest tests.test_schema_migrations

The database name must contain "test".
"""

import io
import os
import json
import shutil
import asyncio
import tempfile
import unittest

from morm.db import Pool
from morm.fields import Field
from morm.pg_models import BaseCommon
from morm.schema import cli
from morm.schema.engine import is_widening, column_pair_score
from morm.schema.state import Column
from morm.schema.chain import load_chain, write_migration

ENV = {k: os.environ.get(f'MORM_TEST_PG{k.upper()}') for k in ('host', 'port', 'user', 'password', 'database')}
ENABLED = (os.environ.get('MORM_TEST_ALLOW_RESET') == '1' and ENV['database'] and 'test' in ENV['database'])


def mk(table, meta=None, **fields):
    Meta = type('Meta', (), dict(db_table=table, **(meta or {})))
    return type('M_' + table, (BaseCommon,), dict(Meta=Meta, **fields))


class TestPure(unittest.TestCase):
    def test_widening(self):
        self.assertTrue(is_widening('character varying(10)', 'character varying(20)'))
        self.assertTrue(is_widening('character varying(10)', 'text'))
        self.assertFalse(is_widening('character varying(20)', 'character varying(10)'))
        self.assertFalse(is_widening('text', 'character varying(10)'))
        self.assertTrue(is_widening('integer', 'bigint'))
        self.assertFalse(is_widening('bigint', 'integer'))
        self.assertTrue(is_widening('integer[]', 'bigint[]'))
        self.assertTrue(is_widening('numeric(10,2)', 'numeric(12,2)'))
        self.assertFalse(is_widening('numeric(10,2)', 'numeric(10,3)'))
        self.assertFalse(is_widening('timestamp without time zone', 'timestamp with time zone'))
        self.assertFalse(is_widening('character varying(10)', 'integer'))

    def test_pair_score(self):
        a = Column('phone', 'character varying(30)', False, None, position=6)
        same = Column('mobile', 'character varying(30)', False, None, position=6)
        other = Column('bio', 'text', False, None, position=6)
        self.assertGreaterEqual(column_pair_score(a, same)[0], 0.7)
        self.assertLess(column_pair_score(a, other)[0], 0.45)


@unittest.skipUnless(ENABLED, 'set MORM_TEST_PG* and MORM_TEST_ALLOW_RESET=1 to run database tests')
class TestMigrations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        kw = {k: v for k, v in ENV.items() if v}
        if 'port' in kw:
            kw['port'] = int(kw['port'])
        cls.pool = Pool(dsn=None, min_size=1, max_size=3, **kw)
        cls.loop = asyncio.get_event_loop()

    def setUp(self):
        self.base = tempfile.mkdtemp(prefix='morm_mg_')
        self.sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    # helpers
    def sql(self, q, *args, fetch=False):
        async def f():
            async with self.pool.pool.acquire() as con:
                if fetch:
                    return await con.fetch(q, *args)
                return await con.execute(q, *args)
        return self.loop.run_until_complete(f())

    def run_mgr(self, models, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = cli.run(self.pool, self.base, models, list(argv), out=out, err=err, interactive=False)
        self.out, self.err = out.getvalue(), err.getvalue()
        return code

    def make_and_migrate(self, models, *decide):
        args = ['makemigrations'] + [f'--decide={d}' for d in decide]
        self.assertEqual(self.run_mgr(models, *args), cli.OK, self.out + self.err)
        self.assertEqual(self.run_mgr(models, 'migrate', '--yes'), cli.OK, self.out + self.err)
        self.assertEqual(self.run_mgr(models, 'verify'), cli.OK, self.out + self.err)

    def last_up(self):
        ch = load_chain(self.base)
        return ch.migrations[-1].up_sql

    def v1(self):
        return mk('users', name=Field('varchar(50)'), phone=Field('varchar(30)'), age=Field('varchar(10)'),
                  note=Field('text'), city=Field('varchar(40)'))

    # tests
    def test_create_noop_and_guards(self):
        U = self.v1()
        self.assertEqual(self.run_mgr([U], 'makemigrations'), cli.OK, self.err)
        self.assertIn('CREATE TABLE "users"', self.last_up())
        self.assertEqual(self.run_mgr([U], 'status', '--json'), cli.OK)
        self.assertEqual(json.loads(self.out)['state'], 'behind')
        self.assertEqual(self.run_mgr([U], 'makemigrations'), cli.REFUSED)   # behind
        self.assertEqual(self.run_mgr([U], 'migrate'), cli.REFUSED)          # no --yes, no tty
        self.assertEqual(self.run_mgr([U], 'migrate', '--yes'), cli.OK, self.err)
        self.assertEqual(self.run_mgr([U], 'makemigrations'), cli.OK)
        self.assertIn('No changes', self.out)
        self.assertEqual(len(load_chain(self.base).migrations), 1)
        self.assertEqual(self.run_mgr([U], 'verify'), cli.OK, self.out)

    def test_drop_and_add_at_same_position_is_not_a_rename(self):
        self.make_and_migrate([self.v1()])
        self.sql("INSERT INTO users(name, phone, updated_at) VALUES ('a', '123', now())")
        U2 = mk('users', name=Field('varchar(50)'), bio=Field('text'), age=Field('varchar(10)'),
                note=Field('text'), city=Field('varchar(40)'))
        self.assertEqual(self.run_mgr([U2], 'makemigrations', '--json'), cli.DECISIONS)
        res = json.loads(self.out)
        self.assertEqual(res['open_decisions'], ['col:users.phone'])
        ev = res['decisions'][0]['evidence']
        self.assertTrue(ev['old_has_data'])
        self.assertFalse(any('RENAME' in s for s in res['up']))
        self.make_and_migrate([U2], 'col:users.phone=drop')

    def test_same_type_rename_needs_an_answer_and_keeps_data(self):
        self.make_and_migrate([self.v1()])
        self.sql("INSERT INTO users(name, phone, updated_at) VALUES ('a', '123', now())")
        U2 = mk('users', name=Field('varchar(50)'), mobile=Field('varchar(30)'), age=Field('varchar(10)'),
                note=Field('text'), city=Field('varchar(40)'))
        self.assertEqual(self.run_mgr([U2], 'makemigrations', '--plan', '--json'), cli.DECISIONS)
        res = json.loads(self.out)
        d = res['decisions'][0]
        self.assertEqual((d['id'], d['recommended']), ('col:users.phone->mobile', 'rename'))
        self.assertEqual(load_chain(self.base).migrations.__len__(), 1)  # nothing written
        self.make_and_migrate([U2], 'col:users.phone->mobile=rename')
        self.assertIn('RENAME COLUMN "phone" TO "mobile"', self.last_up())
        self.assertEqual(self.sql('SELECT mobile FROM users', fetch=True)[0]['mobile'], '123')

    def test_middle_changes_touch_nothing_else(self):
        self.make_and_migrate([self.v1()])
        U2 = mk('users', top=Field('integer'), name=Field('varchar(50)'), age=Field('varchar(10)'),
                extra=Field('boolean'), note=Field('text'), city=Field('varchar(40)'))
        self.make_and_migrate([U2], 'col:users.phone=drop')
        up = self.last_up()
        body = [l for l in up.splitlines() if l and not l.startswith('--')]
        self.assertEqual(len(body), 3, up)
        for col in ('name', 'age', 'note', 'city'):
            self.assertNotIn(f'"{col}"', '\n'.join(body))

    def test_five_changes_at_once(self):
        C = mk('companies', symbol=Field('varchar(20)', sql_onadd='NOT NULL UNIQUE'))
        U = mk('users', {'unique_groups': {'np': ['name', 'phone']}},
               name=Field('varchar(50)', index='hash'), phone=Field('varchar(30)'), age=Field('varchar(10)'),
               note=Field('text'), city=Field('varchar(40)'),
               sym=Field('varchar(20)', sql_onadd='REFERENCES companies(symbol) ON DELETE CASCADE'))
        self.make_and_migrate([U, C])
        self.sql("INSERT INTO companies(symbol, updated_at) VALUES ('X', now());"
                 "INSERT INTO users(name, phone, age, note, sym, updated_at) VALUES ('a','1','30','n','X',now())")
        U2 = mk('users', {'unique_groups': {'nb': ['name', 'bio']}},
                name=Field('varchar(80)', index='btree'), bio=Field('text'), age=Field('integer'),
                notes=Field('text'), town=Field('varchar(40)'),
                sym=Field('varchar(20)', sql_onadd='REFERENCES companies(symbol) ON DELETE CASCADE'))
        self.assertEqual(self.run_mgr([U2, C], 'makemigrations', '--json'), cli.DECISIONS)
        ids = set(json.loads(self.out)['open_decisions'])
        self.assertEqual(ids, {'col:users.phone', 'col:users.note->notes', 'col:users.city->town',
                               'type:users.age', 'idx:users.__IDX_users_name_hash__'})
        self.make_and_migrate([U2, C], 'col:users.phone=drop', 'col:users.note->notes=rename',
                              'col:users.city->town=rename', 'type:users.age=cast',
                              'idx:users.__IDX_users_name_hash__=drop')
        r = self.sql('SELECT age, notes FROM users', fetch=True)[0]
        self.assertEqual((r['age'], r['notes']), (30, 'n'))
        # down works too
        self.assertEqual(self.run_mgr([U2, C], 'rollback', '--yes'), cli.OK, self.err)
        self.assertEqual(self.run_mgr([U, C], 'verify'), cli.ERROR)  # behind: files say 2 migrations
        self.assertEqual(json.loads(self._verify_json([U, C]))['drift'], [])

    def _verify_json(self, models):
        self.run_mgr(models, 'verify', '--json')
        return self.out

    def test_failure_leaves_files_and_ledger_alone(self):
        self.make_and_migrate([self.v1()])
        ch = load_chain(self.base)
        m = write_migration(self.base, ch, ['ALTER TABLE "users" ADD COLUMN "x" integer;', 'SELECT 1/0;'],
                            ['ALTER TABLE "users" DROP COLUMN "x";'], 'bad')
        self.assertEqual(self.run_mgr([self.v1()], 'migrate', '--yes'), cli.ERROR)
        self.assertTrue(os.path.isdir(m.path))
        self.assertEqual(len(self.sql('SELECT 1 FROM _morm_migrations', fetch=True)), 1)
        cols = self.sql("SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='x'",
                        fetch=True)
        self.assertEqual(cols, [])

    def test_orphans_block_and_rollback(self):
        U = self.v1()
        self.make_and_migrate([U])
        U2 = mk('users', name=Field('varchar(50)'), phone=Field('varchar(30)'), age=Field('varchar(10)'),
                note=Field('text'), city=Field('varchar(40)'), branch=Field('text'))
        self.make_and_migrate([U2])
        # switch "branch": the second migration's files disappear
        shutil.rmtree(load_chain(self.base).migrations[-1].path)
        self.assertEqual(self.run_mgr([U], 'status', '--json'), cli.OK)
        self.assertEqual(json.loads(self.out)['state'], 'ahead')
        self.assertEqual(self.run_mgr([U], 'makemigrations'), cli.REFUSED)
        self.assertEqual(self.run_mgr([U], 'migrate', '--yes'), cli.REFUSED)
        self.assertEqual(self.run_mgr([U], 'rollback', '--orphans', '--yes'), cli.OK, self.err)
        self.assertEqual(self.run_mgr([U], 'verify'), cli.OK, self.out)

    def test_diverged_chain_and_rebase(self):
        U = self.v1()
        self.make_and_migrate([U])
        ch = load_chain(self.base)
        write_migration(self.base, ch, ['ALTER TABLE "users" ADD COLUMN "a" text;'],
                        ['ALTER TABLE "users" DROP COLUMN "a";'], 'branch_a')
        write_migration(self.base, ch, ['ALTER TABLE "users" ADD COLUMN "b" text;'],
                        ['ALTER TABLE "users" DROP COLUMN "b";'], 'branch_b', number=3)
        self.assertEqual(self.run_mgr([U], 'check'), cli.ERROR)
        self.assertIn('diverged', self.out)
        self.assertEqual(self.run_mgr([U], 'migrate', '--yes'), cli.REFUSED)
        self.assertEqual(self.run_mgr([U], 'rebase-chain', '--yes'), cli.OK, self.err)
        ch = load_chain(self.base)
        self.assertTrue(ch.linear, ch.problems)
        self.assertEqual(len(ch.migrations), 3)
        self.assertEqual(self.run_mgr([U], 'migrate', '--yes'), cli.OK, self.err)

    def test_changed_after_apply(self):
        self.make_and_migrate([self.v1()])
        m = load_chain(self.base).migrations[-1]
        with open(os.path.join(m.path, 'up.sql'), 'a') as f:
            f.write('-- edited\n')
        self.assertEqual(self.run_mgr([self.v1()], 'migrate', '--yes', '--strict'), cli.ERROR)
        self.assertEqual(self.run_mgr([self.v1()], 'migrate', '--yes'), cli.OK)
        self.assertIn('changed on disk', self.err)

    def test_hooks(self):
        U = self.v1()
        self.make_and_migrate([U])
        self.sql("INSERT INTO users(name, updated_at) VALUES ('a', now())")
        U2 = mk('users', name=Field('varchar(50)'), phone=Field('varchar(30)'), age=Field('varchar(10)'),
                note=Field('text'), city=Field('varchar(40)'), slug=Field('text'))
        self.assertEqual(self.run_mgr([U2], 'makemigrations'), cli.OK, self.err)
        m = load_chain(self.base).migrations[-1]
        with open(os.path.join(m.path, 'hooks.py'), 'w') as f:
            f.write('async def after(db):\n'
                    '    await db.execute("UPDATE users SET slug = lower(name)")\n')
        self.assertEqual(self.run_mgr([U2], 'migrate', '--yes'), cli.OK, self.err)
        self.assertEqual(self.sql('SELECT slug FROM users', fetch=True)[0]['slug'], 'a')

    def test_baseline_existing_and_fresh(self):
        U = self.v1()
        # an existing database made by some other means (old morm)
        self.sql('CREATE TABLE users (id serial PRIMARY KEY NOT NULL, created_at timestamptz NOT NULL '
                 'DEFAULT now(), updated_at timestamptz NOT NULL, name varchar(50), phone varchar(30), '
                 'age varchar(10), note text, city varchar(40))')
        self.assertEqual(self.run_mgr([U], 'baseline', '--yes'), cli.OK, self.out + self.err)
        self.assertEqual(self.run_mgr([U], 'verify'), cli.OK, self.out)
        self.assertEqual(load_chain(self.base).migrations[0].dirname, '0000_baseline')
        # a fresh database gets everything from the baseline
        self.sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
        self.assertEqual(self.run_mgr([U], 'migrate', '--yes'), cli.OK, self.err)
        self.assertEqual(self.run_mgr([U], 'verify'), cli.OK, self.out)

    def test_baseline_refuses_on_drift(self):
        self.sql('CREATE TABLE users (id serial PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now(), '
                 'updated_at timestamptz NOT NULL, name varchar(99))')
        self.assertEqual(self.run_mgr([self.v1()], 'baseline', '--yes'), cli.ERROR)
        self.assertIn('drift', self.out)
        self.assertEqual(load_chain(self.base).migrations, [])

    def test_decimal_and_dict_defaults_become_sql_defaults(self):
        from decimal import Decimal
        U = mk('alerts', pct=Field('numeric', max_digits=6, decimal_places=2, default=Decimal('4')),
               cur=Field('jsonb', default={}))
        self.make_and_migrate([U])
        rows = self.sql("SELECT column_name, column_default FROM information_schema.columns "
                        "WHERE table_name='alerts' AND column_name IN ('pct', 'cur') ORDER BY 1", fetch=True)
        self.assertEqual([r['column_default'] for r in rows], ["'{}'::jsonb", '(4)::numeric(6,2)'])

    def test_bad_model_sql_names_the_model(self):
        U = mk('broken', x=Field('integer', sql_alter=('ALTER TABLE "{table}" ADD CONSTRAINT c CHECK (nope > 0)',)))
        self.assertEqual(self.run_mgr([U], 'makemigrations'), cli.ERROR)
        self.assertIn('M_broken', self.err)
        self.assertIn('nope', self.err)

    def test_trial_run_does_not_wait_for_locks(self):
        import time, asyncpg
        self.make_and_migrate([self.v1()])
        U2 = mk('users', name=Field('varchar(50)'), phone=Field('varchar(30)'), age=Field('varchar(10)'),
                note=Field('text'), city=Field('varchar(40)'), more=Field('text'))
        kw = {k: v for k, v in ENV.items() if v}
        kw['port'] = int(kw.get('port', 5432))

        other = self.loop.run_until_complete(asyncpg.connect(**kw))
        tr = other.transaction()
        self.loop.run_until_complete(tr.start())
        self.loop.run_until_complete(other.execute('LOCK TABLE users IN ACCESS SHARE MODE'))
        try:
            t0 = time.monotonic()
            self.assertEqual(self.run_mgr([U2], 'makemigrations', '--plan'), cli.ERROR)
            self.assertLess(time.monotonic() - t0, 20)
            self.assertIn('lock', self.err.lower())
        finally:
            self.loop.run_until_complete(tr.rollback())
            self.loop.run_until_complete(other.close())

    def test_unmanaged_tables_are_left_alone(self):
        self.sql('CREATE TABLE legacy (x int)')
        U = self.v1()
        self.make_and_migrate([U])
        self.assertNotIn('legacy', self.last_up())
        self.assertEqual(self.run_mgr([U], 'makemigrations', '--json'), cli.OK)
        self.assertEqual(json.loads(self.out)['unmanaged_tables'], ['legacy'])
        self.assertEqual(self.run_mgr([U], 'makemigrations', '--decide', 'table:legacy=drop'), cli.OK, self.err)
        self.assertIn('DROP TABLE "legacy"', self.last_up())


if __name__ == '__main__':
    unittest.main()
