# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test saving objects to database and retrieving them."""

import pytest

import asynccachedview.cache.database
import asynccachedview.dataclasses


@asynccachedview.dataclasses.dataclass
class Parent:
    """Example dataclass to represent a parent object."""

    id: int  # noqa: A003

    @classmethod
    async def __obtain__(cls, id_):  # noqa: PLW3201
        return cls(id_)

    @asynccachedview.dataclasses.awaitable_property
    async def children(self):
        """Children objects."""
        return (
            Child(id=0, parent_id=self.id, text='c0'),
            Child(id=1, parent_id=self.id, text='c1'),
        )


@asynccachedview.dataclasses.dataclass
class Child:
    """Example dataclass to represent a child object."""

    id: int  # noqa: A003
    parent_id: int
    text: str

    @classmethod
    async def __obtain__(cls, id_):  # noqa: PLW3201
        return cls(id=id_, parent_id=0, text=f'c{id_}')

    @asynccachedview.dataclasses.awaitable_property
    async def parent(self):
        """Parent object."""
        return await Parent.__obtain__(self.parent_id)


@pytest.mark.asyncio()
async def test_database() -> None:
    """Test database."""
    async with asynccachedview.cache.database.Database() as db:
        p0 = await Parent.__obtain__(0)
        await db.store(p0)

        p0_retrieved = await db.retrieve(Parent, 0)
        assert p0 == p0_retrieved

        c0 = await Child.__obtain__(0)
        c1 = await Child.__obtain__(1)
        await db.store(c0)  # table doesn't exist yet
        await db.store(c0)  # table exists now, upsert
        await db.store(c1)  # table exists now

        c0_retrieved = await db.retrieve(Child, 0)
        c1_retrieved = await db.retrieve(Child, 1)
        assert c0 == c0_retrieved
        assert c1 == c1_retrieved
        assert c1.id == 1
        assert c1.parent_id == 0
        assert await c1.parent == p0
        assert c1.text == 'c1'
