"""Migration files (one global chain) and the ledger of applied migrations.

Layout::

    <base>/<NNNN>_<slug>/up.sql
    <base>/<NNNN>_<slug>/down.sql
    <base>/<NNNN>_<slug>/meta.json     # id, parent, name, checksum, decisions
    <base>/<NNNN>_<slug>/hooks.py      # optional: async before(db), after(db),
                                       #           before_down(db), after_down(db)

The id of a migration never changes; ``parent`` links it to the previous one.
The ledger table ``_morm_migrations`` in the target database records what was
applied there, including the down SQL, so a migration can be rolled back even
when its files are gone from the checkout.
"""

import os
import re
import json
import uuid
import socket
import getpass
import hashlib
import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from morm.schema import LEDGER_TABLE
from morm.utils import import_from_path


DIR_RE = re.compile(r'^(\d{4,})_([A-Za-z0-9_]+)$')


@dataclass
class MigrationFile:
    path: str
    number: int
    name: str
    id: str
    parent: Optional[str]
    up_sql: str
    down_sql: str
    meta: Dict[str, Any]
    hooks_path: Optional[str] = None

    @property
    def dirname(self) -> str:
        return os.path.basename(self.path)

    def checksum(self) -> str:
        return compute_checksum(self.up_sql, self.down_sql, self.hooks_source())

    def hooks_source(self) -> str:
        if self.hooks_path:
            with open(self.hooks_path) as f:
                return f.read()
        return ''

    def hooks(self):
        if not self.hooks_path:
            return None
        return import_from_path(f'morm_hooks_{self.id}', self.hooks_path)


def compute_checksum(up: str, down: str, hooks: str = '') -> str:
    h = hashlib.sha256()
    for part in (up, down, hooks):
        h.update(part.encode())
        h.update(b'\0')
    return h.hexdigest()


@dataclass
class Chain:
    migrations: List[MigrationFile] = field(default_factory=list)   # in chain order when linear
    problems: List[str] = field(default_factory=list)
    heads: List[str] = field(default_factory=list)
    legacy_dirs: List[str] = field(default_factory=list)

    @property
    def by_id(self) -> Dict[str, MigrationFile]:
        return {m.id: m for m in self.migrations}

    @property
    def head(self) -> Optional[str]:
        return self.heads[0] if len(self.heads) == 1 else None

    @property
    def linear(self) -> bool:
        return not self.problems


def load_chain(base: str) -> Chain:
    ch = Chain()
    if not os.path.isdir(base):
        return ch
    files: List[MigrationFile] = []
    for d in sorted(os.listdir(base)):
        p = os.path.join(base, d)
        if not os.path.isdir(p):
            continue
        m = DIR_RE.match(d)
        if not m:
            if os.path.isdir(os.path.join(p, '.queue')):
                ch.legacy_dirs.append(d)
            continue
        try:
            with open(os.path.join(p, 'meta.json')) as f:
                meta = json.load(f)
            with open(os.path.join(p, 'up.sql')) as f:
                up = f.read()
            with open(os.path.join(p, 'down.sql')) as f:
                down = f.read()
        except (OSError, ValueError) as e:
            ch.problems.append(f'{d}: unreadable migration ({e})')
            continue
        hp = os.path.join(p, 'hooks.py')
        files.append(MigrationFile(p, int(m.group(1)), m.group(2), meta['id'], meta.get('parent'),
                                   up, down, meta, hp if os.path.isfile(hp) else None))
    ids: Dict[str, MigrationFile] = {}
    for f in files:
        if f.id in ids:
            ch.problems.append(f'{f.dirname} and {ids[f.id].dirname} have the same id {f.id}')
        ids[f.id] = f
    children: Dict[Optional[str], List[MigrationFile]] = {}
    for f in files:
        if f.parent is not None and f.parent not in ids:
            ch.problems.append(f'{f.dirname}: parent {f.parent} does not exist')
        children.setdefault(f.parent, []).append(f)
    for parent, kids in children.items():
        if len(kids) > 1:
            names = ', '.join(k.dirname for k in kids)
            ch.problems.append(f'diverged: {names} all follow {_label(parent, ids)} '
                               f'(run rebase-chain)')
    ch.heads = [f.id for f in files if f.id not in children]
    # walk from the root following first children
    order: List[MigrationFile] = []
    cur = children.get(None, [])
    seen = set()
    while cur:
        nxt = sorted(cur, key=lambda x: x.number)[0]
        if nxt.id in seen:
            ch.problems.append('cycle in migration parents')
            break
        seen.add(nxt.id)
        order.append(nxt)
        cur = children.get(nxt.id, [])
    order += [f for f in files if f.id not in seen]
    ch.migrations = order
    return ch


def _label(mid: Optional[str], ids: Dict[str, MigrationFile]) -> str:
    if mid is None:
        return 'the start'
    return ids[mid].dirname if mid in ids else mid


def slugify(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower()
    return (s or 'auto')[:60]


def auto_name(up: List[str]) -> str:
    words = []
    for stmt in up[:4]:
        m = re.match(r'(CREATE TABLE|DROP TABLE|ALTER TABLE)\s+"([^"]+)"\s*(\w+)?(?:\s+(?:COLUMN|CONSTRAINT)?\s*"?([^"\s;]+))?', stmt)
        if m:
            kind, t, verb, obj = m.groups()
            if kind == 'CREATE TABLE':
                words.append(f'create_{t}')
            elif kind == 'DROP TABLE':
                words.append(f'drop_{t}')
            else:
                words.append(f'{t}_{(verb or "").lower()}_{obj or ""}')
    return slugify('_'.join(words) or 'auto')


def render_sql(stmts: List[str], header: List[str]) -> str:
    head = ''.join(f'-- {h}\n' for h in header)
    return head + ('\n' if head else '') + '\n'.join(stmts) + ('\n' if stmts else '')


def write_migration(base: str, chain: Chain, up: List[str], down: List[str],
                    name: str = '', decisions: List[Dict[str, Any]] = (), notes: List[str] = (),
                    number: Optional[int] = None) -> MigrationFile:
    os.makedirs(base, exist_ok=True)
    if number is None:
        number = max([m.number for m in chain.migrations], default=0) + 1
    slug = slugify(name) if name else auto_name(up)
    path = os.path.join(base, f'{number:04d}_{slug}')
    os.makedirs(path)
    header = [f'morm migration {number:04d}_{slug}']
    for d in decisions:
        header.append(f'decision {d["id"]} = {d["choice"]} (recommended {d["recommended"]}): {d["summary"]}')
        ev = {k: v for k, v in d.get('evidence', {}).items() if k not in ('old', 'new')}
        if ev:
            header.append(f'    evidence: {json.dumps(ev, default=str, sort_keys=True)}')
    for n in notes:
        header.append(f'note: {n}')
    up_sql = render_sql(up, header)
    down_sql = render_sql(down, [f'down of {number:04d}_{slug}'])
    meta = {
        'id': uuid.uuid4().hex[:16],
        'parent': chain.head,
        'name': slug,
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'checksum': compute_checksum(up_sql, down_sql, ''),
        'decisions': list(decisions),
    }
    with open(os.path.join(path, 'up.sql'), 'w') as f:
        f.write(up_sql)
    with open(os.path.join(path, 'down.sql'), 'w') as f:
        f.write(down_sql)
    with open(os.path.join(path, 'meta.json'), 'w') as f:
        json.dump(meta, f, indent=2, default=str)
        f.write('\n')
    return MigrationFile(path, number, slug, meta['id'], meta['parent'], up_sql, down_sql, meta)


def rewrite_meta(m: MigrationFile, **changes):
    m.meta.update(changes)
    with open(os.path.join(m.path, 'meta.json'), 'w') as f:
        json.dump(m.meta, f, indent=2, default=str)
        f.write('\n')


# ---------------------------------------------------------------- ledger

LEDGER_DDL = f'''
CREATE TABLE IF NOT EXISTS "{LEDGER_TABLE}" (
    seq bigserial PRIMARY KEY,
    id text NOT NULL UNIQUE,
    name text NOT NULL,
    parent text,
    checksum text NOT NULL,
    up_sql text NOT NULL,
    down_sql text NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    applied_by text,
    host text
)'''

LOCK_KEY = 0x6d6f726d  # 'morm'


@dataclass
class LedgerRow:
    seq: int
    id: str
    name: str
    parent: Optional[str]
    checksum: str
    down_sql: str
    applied_at: Any
    applied_by: Optional[str]
    host: Optional[str]


async def ledger_exists(con) -> bool:
    return bool(await con.fetchval('SELECT to_regclass($1) IS NOT NULL', f'"{LEDGER_TABLE}"'))


async def ensure_ledger(con):
    await con.execute(LEDGER_DDL)


async def read_ledger(con) -> List[LedgerRow]:
    if not await ledger_exists(con):
        return []
    rows = await con.fetch(f'SELECT seq, id, name, parent, checksum, down_sql, applied_at, applied_by, host '
                           f'FROM "{LEDGER_TABLE}" ORDER BY seq')
    return [LedgerRow(**dict(r)) for r in rows]


async def record(con, m: MigrationFile):
    await con.execute(
        f'INSERT INTO "{LEDGER_TABLE}" (id, name, parent, checksum, up_sql, down_sql, applied_by, host) '
        'VALUES ($1, $2, $3, $4, $5, $6, $7, $8)',
        m.id, m.dirname, m.parent, m.checksum(), m.up_sql, m.down_sql, _who(), socket.gethostname())


async def unrecord(con, mid: str):
    await con.execute(f'DELETE FROM "{LEDGER_TABLE}" WHERE id = $1', mid)


def _who() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ''


# ---------------------------------------------------------------- status

@dataclass
class Status:
    chain: Chain
    ledger: List[LedgerRow]
    pending: List[MigrationFile] = field(default_factory=list)
    orphans: List[LedgerRow] = field(default_factory=list)
    out_of_order: List[MigrationFile] = field(default_factory=list)
    changed: List[MigrationFile] = field(default_factory=list)

    @property
    def state(self) -> str:
        if not self.chain.linear:
            return 'diverged'
        if self.orphans:
            return 'ahead'
        if self.pending:
            return 'behind'
        return 'in_sync'

    def to_json(self) -> Dict[str, Any]:
        return {
            'state': self.state,
            'problems': self.chain.problems,
            'pending': [m.dirname for m in self.pending],
            'out_of_order': [m.dirname for m in self.out_of_order],
            'orphans': [{'id': r.id, 'name': r.name, 'applied_at': str(r.applied_at),
                         'applied_by': r.applied_by, 'host': r.host} for r in self.orphans],
            'changed_after_apply': [m.dirname for m in self.changed],
            'applied': len(self.ledger),
            'legacy_dirs': self.chain.legacy_dirs,
        }


def compute_status(chain: Chain, ledger: List[LedgerRow]) -> Status:
    st = Status(chain, ledger)
    applied = {r.id: r for r in ledger}
    ids = chain.by_id
    st.orphans = [r for r in ledger if r.id not in ids]
    last_applied_idx = -1
    for i, m in enumerate(chain.migrations):
        if m.id in applied:
            last_applied_idx = i
            if applied[m.id].checksum != m.checksum():
                st.changed.append(m)
    for i, m in enumerate(chain.migrations):
        if m.id not in applied:
            st.pending.append(m)
            if i < last_applied_idx:
                st.out_of_order.append(m)
    return st
