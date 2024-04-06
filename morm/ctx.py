
from asyncpg import exceptions
from collections.abc import Sequence

async def set_type_codecs(conn, type_codecs):
    for codec in type_codecs:
        if not isinstance(codec['type'], Sequence):
            codec['type'] = (codec['type'],)
        for t in codec['type']:
            await conn.set_type_codec(t, **codec['kwargs'])

class MormConnectionAcquireContext:

    __slots__ = ('connection', 'done', 'type_codecs')

    def __init__(self, conn, type_codecs=()):
        self.connection = conn
        self.done = False
        self.type_codecs = type_codecs

    async def __aenter__(self):
        if self.done:
            raise exceptions.InterfaceError('The connection is already acquired')
        await set_type_codecs(self.connection, self.type_codecs)
        return self.connection

    async def __aexit__(self, *exc):
        self.done = True
        self.connection = None

    def __await__(self):
        self.done = True
        set_type_codecs(self.connection, self.type_codecs).__await__()
        return self.connection


class MormPoolAcquireContext:

    __slots__ = ('timeout', 'connection', 'done', 'pool', 'type_codecs')

    def __init__(self, pool, timeout, type_codecs=()):
        self.pool = pool
        self.timeout = timeout
        self.connection = None
        self.done = False
        self.type_codecs = type_codecs

    async def __aenter__(self):
        if self.connection is not None or self.done:
            raise exceptions.InterfaceError('a connection is already acquired')
        self.connection = await self.pool._acquire(self.timeout)
        await set_type_codecs(self.connection, self.type_codecs)
        return self.connection

    async def __aexit__(self, *exc):
        self.done = True
        con = self.connection
        self.connection = None
        await self.pool.release(con)

    def __await__(self):
        self.done = True
        conn = self.pool._acquire(self.timeout).__await__()
        set_type_codecs(conn, self.type_codecs).__await__()
        return conn
