# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import dataclasses
import pathlib

import pytest

import asynccachedview.cache
import asynccachedview.dataclasses


@asynccachedview.dataclasses.dataclass
class ED:
    """Example dataclass."""

    id: int = dataclasses.field(  # noqa: A003
        metadata=asynccachedview.dataclasses.primary_key(),
    )

    @classmethod
    async def __obtain__(cls, id_):  # noqa: PLW3201
        return cls(id=id_)

    @asynccachedview.dataclasses.awaitable_property
    async def self_list(self) -> list['ED']:
        """Return a list instead of a tuple from an awaitable property."""
        return [self, self]

    @asynccachedview.dataclasses.awaitable_property
    async def self_tuple_bound(self) -> tuple['ED', 'ED']:
        """Return a tuple and not a list from an awaitable property."""
        return self, self

    @asynccachedview.dataclasses.awaitable_property
    async def self_tuple_unbound(self) -> tuple['ED', ...]:
        """Return a tuple and not a list from an awaitable property."""
        return self, self, self

    @asynccachedview.dataclasses.awaitable_property
    async def self(self) -> 'ED':
        """Return self from an awaitable property."""
        return self

    @asynccachedview.dataclasses.awaitable_property
    async def primitive_type(self) -> int:  # noqa: PLR6301
        """Return a random type from an awaitable property."""
        return 0

    @asynccachedview.dataclasses.awaitable_property
    async def primitive_type_tuple(self) -> tuple[int, ...]:  # noqa: PLR6301
        """Return a tuple of a random type from an awaitable property."""
        return 0, 0


@pytest.mark.asyncio()
async def test_types_using_cache() -> None:
    """Test various awaitable property return types with a cache."""
    async with asynccachedview.cache.Cache() as acv:
        ed = await acv.obtain(ED, 0)
        assert await ed.self is ed
        assert await ed.self_list == [ed, ed]
        assert await ed.self_tuple_bound == (ed, ed)
        assert await ed.self_tuple_unbound == (ed, ed, ed)
        assert await ed.primitive_type == 0
        assert await ed.primitive_type_tuple == (0, 0)


@pytest.mark.asyncio()
async def test_types_using_cache_twice(tmp_path: pathlib.Path) -> None:
    """Test various awaitable property return types with a reopened cache."""
    async with asynccachedview.cache.Cache(tmp_path / 'db.sqlite') as acv:
        ed = await acv.obtain(ED, 0)
        assert await ed.self is ed
        assert await ed.self_list == [ed, ed]
        assert await ed.self_tuple_bound == (ed, ed)
        assert await ed.self_tuple_unbound == (ed, ed, ed)
        assert await ed.primitive_type == 0
        assert await ed.primitive_type_tuple == (0, 0)
    async with asynccachedview.cache.Cache(tmp_path / 'db.sqlite') as acv:
        ed = await acv.obtain(ED, 0)
        assert await ed.self is ed
        assert await ed.self_tuple_bound == (ed, ed)
        assert await ed.self_tuple_unbound == (ed, ed, ed)
        assert await ed.self_list == [ed, ed]
        assert await ed.primitive_type == 0
        assert await ed.primitive_type_tuple == (0, 0)


@pytest.mark.asyncio()
async def test_types_not_using_cache() -> None:
    """Test various awaitable property return types without a cache."""
    ed = await ED.__obtain__(1)
    assert await ed.self is ed
    assert await ed.self_tuple_bound == (ed, ed)
    assert await ed.self_tuple_unbound == (ed, ed, ed)
    assert await ed.self_list == [ed, ed]
    assert await ed.primitive_type == 0
    assert await ed.primitive_type_tuple == (0, 0)


@pytest.mark.asyncio()
async def test_nocache() -> None:
    """Test NoCache is the default associated cache."""
    ed0 = await ED.__obtain__(0)
    no_cache = asynccachedview.cache.get_cache(ed0)
    assert no_cache.__name__ == 'NoCache'
    await no_cache.cache(ed0)
    assert asynccachedview.cache.get_cache(ed0) is no_cache


@pytest.mark.asyncio()
async def test_late_association() -> None:
    """Test creating object first and associating it with cache later."""
    ed0 = await ED.__obtain__(0)
    no_cache = asynccachedview.cache.get_cache(ed0)
    assert no_cache.__name__ == 'NoCache'

    async with asynccachedview.cache.Cache() as acv:
        ed1 = await acv.obtain(ED, 1)
        assert asynccachedview.cache.get_cache(ed0) is no_cache
        assert asynccachedview.cache.get_cache(ed1) is acv

        await asynccachedview.cache.get_cache(ed1).cache(ed0)
        assert asynccachedview.cache.get_cache(ed0) is acv
        assert asynccachedview.cache.get_cache(ed1) is acv

        assert await acv.obtain(ED, 0) is ed0
