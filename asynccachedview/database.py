# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements caching objects in an sqlite database."""

import dataclasses
import sqlite3
import types
import typing

import aiosqlite


class Database:
    """Database to persist dataclasses to."""

    def __init__(self, path=None):
        """
        Initialize a database. `async with` to open it.

        `path=None` will use an in-memory database.
        """
        self._db_path = path or ':memory:'
        self._db = None
        self._selectors_cache = {}

    async def __aenter__(self) -> typing.Self:
        self._db = await aiosqlite.connect(self._db_path)
        return self

    async def __aexit__(self,
                        exc_type: typing.Optional[type[BaseException]],
                        exc_val: typing.Optional[BaseException],
                        exc_tb: typing.Optional[types.TracebackType]
                        ) -> None:
        await self._db.close()

    @staticmethod
    def _dataclass_to_dict(obj):
        values = dataclasses.asdict(obj)
        del values['_cache_holder']
        return values

    @staticmethod
    def _tablename(dataclass):
        return dataclass.__qualname__.replace('.', '_')  # ugly

    async def _create_table(self, dataclass):
        all_fields = tuple(f.name for f in dataclasses.fields(dataclass)
                           if f.name != '_cache_holder')
        # pylint: disable-next=protected-access
        identity_fields = dataclass._identity_field_names
        tablename = self._tablename(dataclass)
        async with self._db.cursor() as cur:
            await cur.execute(f'CREATE TABLE {tablename} '
                              f'({", ".join(fn for fn in all_fields)},'
                              f' PRIMARY KEY ('
                              f' {", ".join(fn for fn in identity_fields)}))')

    def _selector(self, dataclass):
        try:
            return self._selectors_cache[dataclass]
        except KeyError:
            pass
        # pylint: disable-next=protected-access
        fields_id = tuple(f'{fn}=?' for fn in dataclass._identity_field_names)
        tablename = self._tablename(dataclass)
        selector = f'SELECT * FROM {tablename} WHERE {" AND ".join(fields_id)}'
        self._selectors_cache[dataclass] = selector
        return selector

    async def _upsert(self, tablename, obj):
        values = tuple(self._dataclass_to_dict(obj).values())
        async with self._db.cursor() as cur:
            await cur.execute(f'INSERT INTO {tablename} '
                              f'VALUES ({", ".join("?" * len(values))})',
                              list(values))
        print('INSERTED', values)

    async def store(self, obj):  # pragma: no cover
        """Persist an object into a database."""
        tablename = self._tablename(obj.__class__)
        try:
            await self._upsert(tablename, obj)
        except sqlite3.OperationalError as ex:  # pragma: no cover
            if ex.args[0] == f'no such table: {tablename}':  # pragma: no cover
                # retry (TODO: more efficiently)
                await self._create_table(obj.__class__)
                await self._upsert(tablename, obj)
            else:  # pragma: no cover
                raise  # pragma: no cover

    async def retrieve(self, dataclass, *identity):
        """Retrieve an object from a database by identity field values."""
        async with self._db.cursor() as cur:
            await cur.execute(self._selector(dataclass), identity)
            res = await cur.fetchone()
            return dataclass(*res)

# TODO: multiprocess-safety
# TODO: efficient store_multi
