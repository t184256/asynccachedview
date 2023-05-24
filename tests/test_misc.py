# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import pytest

import asynccachedview


@asynccachedview.dataclass
class ED:
    """Example dataclass."""

    id: int

    @classmethod
    async def __obtain__(cls, id_):
        return cls(id=id_)

    @asynccachedview.awaitable_property
    async def self_list(self):
        """Return a list instead of a tuple from an awaitable property."""
        return [self, self]

    @asynccachedview.awaitable_property
    async def self_tuple(self):
        """Return a tuple and not a list from an awaitable property."""
        return self, self


@pytest.mark.asyncio
async def test_list_using_cache() -> None:
    """Test our dataclasses operation with a cache."""
    async with asynccachedview.Cache() as acv:
        ed = await acv.obtain(ED, 0)
        assert await ed.self_tuple == (ed, ed)
        with pytest.raises(RuntimeError):
            await ed.self_list


@pytest.mark.asyncio
async def test_list_not_using_cache() -> None:
    """Test our dataclasses operation without a cache."""
    ed = await ED.__obtain__(1)
    assert await ed.self_tuple == (ed, ed)
    await ed.self_list   # does not raise RuntimeError
