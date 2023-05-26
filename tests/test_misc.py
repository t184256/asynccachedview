# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import pytest

import asynccachedview.dataclasses


@asynccachedview.dataclasses.dataclass
class ED:
    """Example dataclass."""

    id: int

    @classmethod
    async def __obtain__(cls, id_):
        return cls(id=id_)

    @asynccachedview.dataclasses.awaitable_property
    async def self_list(self):
        """Return a list instead of a tuple from an awaitable property."""
        return [self, self]

    @asynccachedview.dataclasses.awaitable_property
    async def self_tuple(self):
        """Return a tuple and not a list from an awaitable property."""
        return self, self


@pytest.mark.asyncio
async def test_list_using_cache() -> None:
    """Test our dataclasses operation with a cache."""
    async with asynccachedview.dataclasses.Cache() as acv:
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


@pytest.mark.asyncio
async def test_late_association() -> None:
    """Test creating object first and associating it with cache later."""
    ed0 = await ED.__obtain__(0)
    assert ed0._cache is None  # pylint: disable=protected-access

    async with asynccachedview.dataclasses.Cache() as acv:
        ed1 = await acv.obtain(ED, 1)
        assert ed0._cache is None  # pylint: disable=protected-access
        assert ed1._cache is acv  # pylint: disable=protected-access

        await asynccachedview.dataclasses.associate_related(ed0, ed1)
        assert ed0._cache is None  # pylint: disable=protected-access
        assert ed1._cache is acv  # pylint: disable=protected-access

        await asynccachedview.dataclasses.associate_related(ed1, ed0)
        assert ed0._cache is acv  # pylint: disable=protected-access
        assert ed1._cache is acv  # pylint: disable=protected-access

        assert await acv.obtain(ED, 0) is ed0
