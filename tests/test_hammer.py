# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import asyncio
import dataclasses
import typing

import pytest

import asynccachedview.cache
import asynccachedview.dataclasses

inst_queue: asyncio.Queue[str] = asyncio.Queue()
prop_queue: asyncio.Queue[str] = asyncio.Queue()

N = 100


@dataclasses.dataclass(frozen=True)
class T(asynccachedview.dataclasses.ACVDataclass[[int], 'T']):
    """Example dataclass."""

    id: int = dataclasses.field(
        metadata=asynccachedview.dataclasses.primary_key(),
    )

    @classmethod
    async def __obtain__(cls, id_: int) -> typing.Self:  # noqa: PLW3201
        await asyncio.sleep(0)
        await inst_queue.put('instantiate')
        return cls(id=id_)

    @asynccachedview.dataclasses.awaitable_property
    async def prop(self: typing.Self) -> typing.Self:
        """Return a list instead of a tuple from an awaitable property."""
        await asyncio.sleep(0)
        await prop_queue.put('prop')
        return self


@pytest.mark.asyncio()
async def test_parallel() -> None:
    """Test parallel instantiation and property querying."""
    async with asynccachedview.cache.Cache() as acv:
        first, *rest = await asyncio.gather(
            *[acv.obtain(T, 0) for i in range(N)],
        )
        assert len(rest) == N - 1
        assert all(first is r for r in rest)
        assert inst_queue.qsize() == 1
        assert await inst_queue.get() == 'instantiate'
        assert inst_queue.empty()

        async def get_property(t: T) -> T:
            return await t.prop

        propvals = await asyncio.gather(
            *[get_property(first) for i in range(N)],
        )
        assert len(propvals) == N
        assert all(first is p for p in propvals)
        assert prop_queue.qsize() == 1
        assert await prop_queue.get() == 'prop'
        assert prop_queue.empty()
