"""``mgr`` command line for catalog based migrations.

Exit codes: 0 ok, 1 error or drift, 2 refused by a guard, 3 open decisions.
"""

import os
import sys
import json
import asyncio
import argparse
import subprocess
from typing import Dict, List, Sequence, Any, Optional

from morm.db import Pool, DB
from morm.model import ModelType
from morm.schema import LEDGER_TABLE
from morm.schema.state import differences
from morm.schema.introspect import introspect
from morm.schema.desired import build_desired, check_models, ModelSQLError
from morm.schema.engine import make_plan, EngineError, Plan
from morm.schema import chain as chainmod
from morm.schema.chain import load_chain, compute_status, read_ledger


OK, ERROR, REFUSED, DECISIONS = 0, 1, 2, 3

# A migration that can not get its locks quickly fails (and can be retried)
# instead of queueing behind running queries and blocking everything after it.
LOCK_TIMEOUT = os.environ.get('MORM_LOCK_TIMEOUT', '10s')


class _Exit(Exception):
    def __init__(self, code: int):
        self.code = code


class Manager:
    def __init__(self, pool: Pool, base_path: str, models: Sequence[ModelType], schema: str = 'public',
                 out=sys.stdout, err=sys.stderr, interactive: Optional[bool] = None):
        self.pool = pool
        self.base = base_path
        self.models = list(models)
        self.schema = schema
        self.out = out
        self.err = err
        self.interactive = sys.stdin.isatty() and sys.stdout.isatty() if interactive is None else interactive

    # ------------------------------------------------------------ output
    def p(self, *a):
        print(*a, file=self.out)

    def e(self, *a):
        print(*a, file=self.err)

    def j(self, obj):
        print(json.dumps(obj, indent=2, default=str), file=self.out)

    def confirm(self, msg: str, yes: bool) -> bool:
        if yes:
            return True
        if not self.interactive:
            self.e(f'{msg}\nRefusing without --yes (not running in a terminal).')
            raise _Exit(REFUSED)
        return input(f'{msg} [y/N]: ').strip().lower() in ('y', 'yes')

    # ------------------------------------------------------------ helpers
    async def _status(self, con):
        ch = load_chain(self.base)
        return compute_status(ch, await read_ledger(con))

    def _print_status(self, st):
        self.p(f'state: {st.state}')
        for x in st.chain.problems:
            self.p(f'  problem: {x}')
        if st.chain.legacy_dirs:
            self.p(f'  legacy (morm 3) migration folders found: {", ".join(st.chain.legacy_dirs[:5])}'
                   f'{" ..." if len(st.chain.legacy_dirs) > 5 else ""}; archive them')
        self.p(f'  applied: {len(st.ledger)}, pending: {len(st.pending)}')
        for m in st.pending:
            flag = '  (out of order)' if m in st.out_of_order else ''
            self.p(f'    pending {m.dirname}{flag}')
        for r in st.orphans:
            self.p(f'    orphan {r.name} (id {r.id}) applied {r.applied_at} by {r.applied_by}@{r.host}: '
                   'not in this checkout')
        for m in st.changed:
            self.p(f'    changed after apply: {m.dirname}')

    def _guard(self, st, allow_pending=False):
        if st.chain.problems:
            self._print_status(st)
            self.e('The migration chain is not linear; fix it first (rebase-chain).')
            raise _Exit(REFUSED)
        if st.orphans:
            self._print_status(st)
            self.e('This database has migrations that are not in this checkout. Either check out the branch '
                   'that has them, or undo them with: rollback --orphans')
            raise _Exit(REFUSED)
        if st.pending and not allow_pending:
            self._print_status(st)
            self.e('This database is behind the migration files; run migrate first '
                   '(migrate --plan to see what it does).')
            raise _Exit(REFUSED)

    async def _plan(self, con, answers, using) -> Plan:
        tr = con.transaction()
        await tr.start()
        try:
            desired = await build_desired(con, self.models, self.schema)
            return await make_plan(con, desired, answers, using, self.schema)
        finally:
            await tr.rollback()

    def _print_plan(self, plan: Plan):
        if plan.empty:
            self.p('No changes: the database matches the models.')
        for d in plan.decisions:
            state = f'answered: {d.choice}' if d.choice else 'OPEN'
            self.p(f'\n[{state}] {d.id}\n  {d.summary}')
            for k, v in d.options.items():
                rec = ' (recommended)' if k == d.recommended else ''
                self.p(f'    {k}{rec}: {v}')
            ev = {k: v for k, v in d.evidence.items()}
            if ev:
                self.p(f'  evidence: {json.dumps(ev, default=str, sort_keys=True)}')
        if plan.up:
            self.p('\n-- up' + ('' if not plan.open_decisions else ' (preview with the recommended answers)'))
            for s in plan.up:
                self.p(s)
            self.p('\n-- down')
            for s in plan.down:
                self.p(s)
        for n in plan.notes:
            self.p(f'\nnote: {n}')
        if plan.unmanaged_tables:
            self.p('\nTables without a model (left alone; answer table:<name>=drop to drop one): '
                   + ', '.join(sorted(plan.unmanaged_tables)))
        if plan.open_decisions:
            flags = ' '.join(f"--decide '{d.id}={d.recommended}'" for d in plan.open_decisions)
            self.p(f'\n{len(plan.open_decisions)} open decision(s). Answer them with: {flags}')

    def _plan_json(self, plan: Plan) -> Dict[str, Any]:
        return {
            'empty': plan.empty,
            'up': plan.up, 'down': plan.down,
            'decisions': [d.to_json() for d in plan.decisions],
            'open_decisions': [d.id for d in plan.open_decisions],
            'notes': plan.notes,
            'unmanaged_tables': sorted(plan.unmanaged_tables),
            'answer_with': [f'--decide {d.id}=<option>' for d in plan.open_decisions],
        }

    def _ask(self, plan: Plan, answers: Dict[str, str]):
        for d in plan.open_decisions:
            self.p(f'\n{d.id}: {d.summary}')
            self.p(f'  evidence: {json.dumps(d.evidence, default=str, sort_keys=True)}')
            opts = list(d.options)
            for k in opts:
                self.p(f'    {k}{" (recommended)" if k == d.recommended else ""}: {d.options[k]}')
            destructive = d.recommended in ('drop', 'drop_add')
            while True:
                hint = f'type {d.recommended} to confirm' if destructive else f'Enter = {d.recommended}'
                a = input(f'  choice [{"/".join(opts)}] ({hint}): ').strip()
                if not a and not destructive:
                    a = d.recommended
                if a in d.options:
                    answers[d.id] = a
                    break

    # ------------------------------------------------------------ commands
    async def status(self, args):
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
        if args.json:
            self.j(st.to_json())
        else:
            self._print_status(st)
        return OK

    async def makemigrations(self, args):
        answers, using = _parse_answers(args)
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
            self._guard(st)
            while True:
                plan = await self._plan(con, answers, using)
                if args.accept_recommended:
                    added = [d.id for d in plan.open_decisions if d.recommended not in ('drop', 'drop_add')]
                    if added:
                        answers.update({d.id: d.recommended for d in plan.open_decisions if d.id in added})
                        continue
                if plan.open_decisions and self.interactive and not args.plan and not args.json and not args.yes:
                    self._print_plan(plan)
                    self._ask(plan, answers)
                    continue
                break
        if args.json:
            self.j(self._plan_json(plan))
        else:
            self._print_plan(plan)
        if plan.open_decisions:
            return DECISIONS
        if plan.empty or args.plan:
            return OK
        m = chainmod.write_migration(self.base, st.chain, plan.up, plan.down, args.name,
                                     [d.to_json() for d in plan.decisions], plan.notes)
        self.p(f'\nCreated {os.path.relpath(m.path)}')
        return OK

    async def migrate(self, args):
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
            self._guard(st, allow_pending=True)
            if st.changed:
                names = ', '.join(m.dirname for m in st.changed)
                if args.strict:
                    self.e(f'Applied migrations changed on disk: {names}')
                    return ERROR
                self.e(f'warning: applied migrations changed on disk: {names}')
            if st.out_of_order:
                names = ', '.join(m.dirname for m in st.out_of_order)
                if args.strict:
                    self.e(f'Pending migrations sort before applied ones: {names}')
                    return REFUSED
                self.e(f'warning: applying out of order: {names}')
            if not st.pending:
                self.p('Nothing to migrate.')
                return OK
            if args.plan:
                if args.json:
                    self.j({'pending': [{'name': m.dirname, 'id': m.id, 'up': m.up_sql,
                                         'hooks': bool(m.hooks_path)} for m in st.pending]})
                else:
                    for m in st.pending:
                        self.p(f'== {m.dirname}{" (+hooks.py)" if m.hooks_path else ""}\n{m.up_sql}')
                return OK
            if not self.confirm(f'Apply {len(st.pending)} migration(s)?', args.yes):
                return REFUSED
            await con.execute('SELECT pg_advisory_lock($1)', chainmod.LOCK_KEY)
            try:
                st = await self._status(con)  # someone may have migrated while we waited
                await chainmod.ensure_ledger(con)
                for m in st.pending:
                    hooks = m.hooks()
                    try:
                        async with con.transaction():
                            await con.execute("SELECT set_config('lock_timeout', $1, true)", LOCK_TIMEOUT)
                            db = DB(self.pool, con)
                            if hooks and hasattr(hooks, 'before'):
                                await hooks.before(db)
                            await con.execute(m.up_sql)
                            if hooks and hasattr(hooks, 'after'):
                                await hooks.after(db)
                            await chainmod.record(con, m)
                    except Exception as e:
                        self.e(f'FAILED {m.dirname}: {type(e).__name__}: {e}\n'
                               'It was rolled back; earlier migrations stay applied, files are untouched.')
                        return ERROR
                    self.p(f'applied {m.dirname}')
            finally:
                await con.execute('SELECT pg_advisory_unlock($1)', chainmod.LOCK_KEY)
        return OK

    async def rollback(self, args):
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
            ledger = st.ledger
            if args.orphans:
                targets = list(reversed(st.orphans))
            elif args.to:
                ids = [r.id for r in ledger]
                matches = [r for r in ledger if r.id == args.to or r.name == args.to]
                if not matches:
                    self.e(f'{args.to} is not applied in this database')
                    return ERROR
                idx = ledger.index(matches[0])
                targets = list(reversed(ledger[idx + 1:]))
            else:
                targets = list(reversed(ledger[-args.last:])) if args.last > 0 else []
            if not targets:
                self.p('Nothing to roll back.')
                return OK
            for r in targets:
                self.p(f'will undo {r.name} (applied {r.applied_at})')
                if args.plan:
                    self.p(r.down_sql)
            if args.plan:
                return OK
            if not self.confirm(f'Undo {len(targets)} migration(s)? Data in dropped columns/tables is lost.',
                                args.yes):
                return REFUSED
            files = st.chain.by_id
            await con.execute('SELECT pg_advisory_lock($1)', chainmod.LOCK_KEY)
            try:
                for r in targets:
                    m = files.get(r.id)
                    hooks = m.hooks() if m else None
                    try:
                        async with con.transaction():
                            db = DB(self.pool, con)
                            if hooks and hasattr(hooks, 'before_down'):
                                await hooks.before_down(db)
                            await con.execute(r.down_sql)
                            if hooks and hasattr(hooks, 'after_down'):
                                await hooks.after_down(db)
                            await chainmod.unrecord(con, r.id)
                    except Exception as e:
                        self.e(f'FAILED to undo {r.name}: {type(e).__name__}: {e}')
                        return ERROR
                    self.p(f'undone {r.name}')
            finally:
                await con.execute('SELECT pg_advisory_unlock($1)', chainmod.LOCK_KEY)
        return OK

    async def verify(self, args):
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
            tr = con.transaction()
            await tr.start()
            try:
                desired = await build_desired(con, self.models, self.schema)
                actual = await introspect(con, self.schema)
            finally:
                await tr.rollback()
        diff = differences(actual.subset(desired.tables), desired)
        unmanaged = sorted(set(actual.tables) - set(desired.tables))
        ok = not diff and st.state == 'in_sync'
        if args.json:
            self.j({'ok': ok, 'state': st.state, 'drift': diff, 'unmanaged_tables': unmanaged,
                    'status': st.to_json()})
        else:
            if st.state != 'in_sync':
                self._print_status(st)
            for x in diff:
                self.p(f'drift: {x}   (left = database, right = models)')
            if unmanaged:
                self.p('tables without a model: ' + ', '.join(unmanaged))
            self.p('verify: OK' if ok else 'verify: FAILED')
        return OK if ok else ERROR

    async def baseline(self, args):
        """Record the current schema as migration 0000 without running it."""
        async with self.pool.pool.acquire() as con:
            st = await self._status(con)
            if st.ledger or st.chain.migrations:
                self.e('baseline is only for a database and checkout without migrations.')
                return REFUSED
            tr = con.transaction()
            await tr.start()
            try:
                desired = await build_desired(con, self.models, self.schema)
                actual = await introspect(con, self.schema)
                diff = differences(actual.subset(desired.tables), desired)
                empty = f'_morm_empty_{os.getpid()}'
                await con.execute(f'CREATE SCHEMA "{empty}"')
                desired_e = await build_desired(con, self.models, empty)
                plan = await make_plan(con, desired_e, {}, {}, empty)
            finally:
                await tr.rollback()
            missing = [t for t in desired.tables if t not in actual.tables]
            if diff and len(missing) != len(desired.tables):
                for x in diff:
                    self.p(f'drift: {x}   (left = database, right = models)')
                self.e('The database does not match the models; fix the models (or the database) until '
                       'verify is clean, then run baseline again.')
                return ERROR
            fresh = len(missing) == len(desired.tables)
            m = chainmod.write_migration(self.base, st.chain, plan.up, plan.down, 'baseline', [], [], number=0)
            self.p(f'Created {os.path.relpath(m.path)}')
            if fresh:
                self.p('The database has none of the model tables; run migrate to create them.')
                return OK
            if not self.confirm('Record the baseline as applied in this database (nothing is executed)?',
                                args.yes):
                return REFUSED
            await chainmod.ensure_ledger(con)
            await chainmod.record(con, m)
            self.p('Baseline recorded as applied.')
        return OK

    def check(self, args):
        problems: List[str] = []
        ch = load_chain(self.base)
        problems += ch.problems
        try:
            check_models(self.models)
        except ModelSQLError as e:
            problems.append(str(e))
        if os.path.isdir(self.base):
            try:
                r = subprocess.run(['git', 'status', '--porcelain', '--', '.'], cwd=self.base,
                                   capture_output=True, text=True, timeout=30)
                if r.returncode == 0 and r.stdout.strip():
                    problems.append('uncommitted changes in the migrations folder:\n' + r.stdout.rstrip())
            except (OSError, subprocess.SubprocessError):
                pass
        if ch.legacy_dirs:
            self.p(f'note: legacy (morm 3) migration folders: {len(ch.legacy_dirs)}')
        for x in problems:
            self.p(f'problem: {x}')
        self.p('check: OK' if not problems else 'check: FAILED')
        return OK if not problems else ERROR

    def rebase_chain(self, args):
        ch = load_chain(self.base)
        ids = ch.by_id
        children: Dict[Optional[str], List[chainmod.MigrationFile]] = {}
        for m in ch.migrations:
            children.setdefault(m.parent, []).append(m)
        forks = {p: k for p, k in children.items() if len(k) > 1}
        if not forks:
            self.p('The chain is linear; nothing to do.')
            return OK
        if len(forks) > 1 or len(next(iter(forks.values()))) > 2:
            self.e('More than two branches; rebase them one at a time with --move.')
            if not args.move:
                return REFUSED
        parent, kids = next(iter(forks.items()))

        def branch(start):
            out = [start]
            while children.get(out[-1].id):
                out.append(sorted(children[out[-1].id], key=lambda x: x.number)[0])
            return out
        if args.move:
            start = next((k for k in kids if args.move in (k.id, k.dirname)), None)
            if not start:
                self.e(f'{args.move} is not the first migration of a branch after the fork')
                return ERROR
        else:
            start = max(kids, key=lambda k: k.meta.get('created_at', ''))
        moving = branch(start)
        staying = branch(next(k for k in kids if k is not start))
        self.p('keeping:  ' + ', '.join(m.dirname for m in staying))
        self.p('moving:   ' + ', '.join(m.dirname for m in moving) + f'  onto {staying[-1].dirname}')
        if not self.confirm('Rewrite parents and numbers of the moved migrations?', args.yes):
            return REFUSED
        number = max(m.number for m in ch.migrations)
        prev = staying[-1].id
        for m in moving:
            number += 1
            chainmod.rewrite_meta(m, parent=prev)
            newpath = os.path.join(self.base, f'{number:04d}_{m.name}')
            os.rename(m.path, newpath)
            m.path = newpath
            prev = m.id
            self.p(f'  -> {m.dirname}')
        self.p('Done. If the moved migrations are applied in your database, migrate will now apply the other '
               'branch out of order; run verify afterwards.')
        return OK


def _parse_answers(args) -> (Dict[str, str], Dict[str, str]):
    answers: Dict[str, str] = {}
    using: Dict[str, str] = {}
    if getattr(args, 'decisions', None):
        with open(args.decisions) as f:
            data = json.load(f)
        for k, v in data.items():
            if isinstance(v, dict):
                answers[k] = v['choice']
                if v.get('using'):
                    using[k] = v['using']
            else:
                answers[k] = v
    for d in getattr(args, 'decide', None) or []:
        if '=' not in d:
            raise SystemExit(f'--decide expects ID=OPTION, got {d!r}')
        k, v = d.rsplit('=', 1)
        answers[k] = v
    for u in getattr(args, 'using', None) or []:
        k, v = u.split('=', 1)
        using[k] = v
    return answers, using


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='mgr', description='morm migrations (catalog based)')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('status', help='compare the database ledger with the migration files')
    s.add_argument('--json', action='store_true')

    s = sub.add_parser('makemigrations', help='diff the models against the database and write a migration')
    s.add_argument('--plan', action='store_true', help='show what would be generated; write nothing')
    s.add_argument('--json', action='store_true', help='machine readable output (implies no prompts)')
    s.add_argument('--decide', action='append', metavar='ID=OPTION', help='answer a decision')
    s.add_argument('--decisions', metavar='FILE', help='JSON file {id: option | {choice, using}}')
    s.add_argument('--using', action='append', metavar='ID=EXPR', help='USING expression for a type decision')
    s.add_argument('--accept-recommended', action='store_true',
                   help='answer open decisions with their recommendation, except drops')
    s.add_argument('--name', default='', help='migration name (slug)')
    s.add_argument('-y', '--yes', action='store_true',
                   help='never prompt (open decisions still stop with exit code 3)')

    s = sub.add_parser('migrate', help='apply pending migrations')
    s.add_argument('--plan', action='store_true', help='list pending migrations and their SQL; change nothing')
    s.add_argument('--json', action='store_true')
    s.add_argument('-y', '--yes', action='store_true')
    s.add_argument('--strict', action='store_true',
                   help='fail when applied files changed or pending migrations are out of order')

    s = sub.add_parser('rollback', help='undo applied migrations using the down SQL stored in the database')
    g = s.add_mutually_exclusive_group()
    g.add_argument('--last', type=int, default=1, help='undo the last N (default 1)')
    g.add_argument('--to', metavar='ID_OR_NAME', help='undo everything applied after this one')
    g.add_argument('--orphans', action='store_true', help='undo migrations that are not in this checkout')
    s.add_argument('--plan', action='store_true')
    s.add_argument('-y', '--yes', action='store_true')

    s = sub.add_parser('verify', help='fail if the database differs from the models or the files')
    s.add_argument('--json', action='store_true')

    sub.add_parser('check', help='offline checks: linear chain, checksums, committed files, models')

    s = sub.add_parser('rebase-chain', help='put one branch of a diverged chain after the other')
    s.add_argument('--move', metavar='ID_OR_DIR', help='first migration of the branch to move')
    s.add_argument('-y', '--yes', action='store_true')

    s = sub.add_parser('baseline', help='start migrations for an existing database (records 0000_baseline)')
    s.add_argument('-y', '--yes', action='store_true')
    return p


def run(pool: Pool, base_path: str, models: Sequence[ModelType], argv: Optional[List[str]] = None,
        schema: str = 'public', **kw) -> int:
    args = build_parser().parse_args(argv)
    mgr = Manager(pool, base_path, models, schema, **kw)
    if getattr(args, 'json', False):
        mgr.interactive = False
    try:
        if args.cmd == 'check':
            return mgr.check(args)
        if args.cmd == 'rebase-chain':
            return mgr.rebase_chain(args)
        fn = getattr(mgr, args.cmd.replace('-', '_'))
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(fn(args))
    except _Exit as e:
        return e.code
    except (EngineError, ModelSQLError) as e:
        mgr.e(f'error: {e}')
        return ERROR


def migration_manager(pool: Pool, base_path: str, models: Sequence[ModelType], schema: str = 'public'):
    """Entry point for a project's ``mgr.py``; exits with the command's code."""
    sys.exit(run(pool, base_path, models, schema=schema))
