# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test accessing an HTTP resource."""

import dataclasses
import http
import pathlib
import typing

import aiohttp
import aioresponses
import asyncio_loop_local
import pytest

import asynccachedview.cache
import asynccachedview.dataclasses
from asynccachedview._nocache import NoCache

ClientSession = asyncio_loop_local.sticky_singleton_acm(aiohttp.ClientSession)


@dataclasses.dataclass(frozen=True)
class Post(asynccachedview.dataclasses.ACVDataclass[[int], 'Post']):
    """Example dataclass to represent a blog post."""

    id: int = dataclasses.field(
        metadata=asynccachedview.dataclasses.primary_key(),
    )

    text: str

    @classmethod
    async def __obtain__(cls, id_: int) -> typing.Self:  # noqa: PLW3201
        async with (
            ClientSession() as sess,
            sess.get('http://ex.ample/post', params={'id': id_}) as resp,
        ):
            assert resp.status == http.HTTPStatus.OK
            j = await resp.json()
            assert j['id'] == id_
            return cls(id_, j['text'])

    @asynccachedview.dataclasses.awaitable_property
    async def comments(self) -> tuple['Comment', ...]:
        """Blog post's comments."""
        async with (
            ClientSession() as sess,
            sess.get(
                'http://ex.ample/comments',
                params={'post_id': self.id},
            ) as resp,
        ):
            assert resp.status == http.HTTPStatus.OK
            j = await resp.json()
            return tuple(
                Comment(id=c['id'], post_id=self.id, text=c['text']) for c in j
            )


@dataclasses.dataclass(frozen=True)
class Comment(asynccachedview.dataclasses.ACVDataclass[[int], 'Comment']):
    """Example dataclass to represent a blog post's comment."""

    id: int = dataclasses.field(
        metadata=asynccachedview.dataclasses.primary_key(),
    )
    post_id: int
    text: str

    @classmethod
    async def __obtain__(cls, id_: int) -> typing.Self:  # noqa: PLW3201
        async with (
            ClientSession() as sess,
            sess.get('http://ex.ample/comment', params={'id': id_}) as resp,
        ):
            assert resp.status == http.HTTPStatus.OK
            j = await resp.json()
            assert j['id'] == id_
            return cls(id_, j['post_id'], j['text'])

    @asynccachedview.dataclasses.awaitable_property
    async def post(self) -> 'Post':
        """Parent post."""
        cache = asynccachedview.cache.get_cache(self)
        return await cache.obtain(Post, self.post_id)


def setup_mocked_data(mocked: aioresponses.core.aioresponses) -> None:
    """Configure `aioresponses.aioresponses()` to output example data."""
    mocked.get(
        'http://ex.ample/post?id=0',
        status=200,
        payload={'id': 0, 'text': 'post0'},
        repeat=True,
    )
    mocked.get(
        'http://ex.ample/comments?post_id=0',
        status=200,
        payload=[
            {'id': 0, 'post_id': 0, 'text': 'comment0'},
            {'id': 1, 'post_id': 0, 'text': 'comment1'},
        ],
        repeat=True,
    )
    mocked.get(
        'http://ex.ample/comment?id=0',
        status=200,
        payload={'id': 0, 'post_id': 0, 'text': 'comment0'},
        repeat=True,
    )
    mocked.get(
        'http://ex.ample/comment?id=1',
        status=200,
        payload={'id': 1, 'post_id': 0, 'text': 'comment1'},
        repeat=True,
    )


@pytest.mark.asyncio()
async def test_using_cache() -> None:
    """Test our dataclasses operation with a cache."""
    async with asynccachedview.cache.Cache() as acv:
        with aioresponses.aioresponses() as mocked:
            setup_mocked_data(mocked)
            # basic querying
            p0 = await acv.obtain(Post, 0)
            assert p0.id == 0
            assert p0.text == 'post0'
            # querying of children: by id
            c0 = await acv.obtain(Comment, 0)
            # querying of children: with an async getter
            comments = await p0.comments
            assert [c.id for c in comments] == [0, 1]
            assert [c.text for c in comments] == ['comment0', 'comment1']
            # identity checks: children obtained differently are same objects
            assert comments[0] is c0
            c1 = await acv.obtain(Comment, 1)
            assert comments[1] is c1
            # identity checks: parents are the same parent object
            assert await comments[0].post is p0
            assert await comments[1].post is p0
            # check that all the objects are cached (TODO: check offline)
            assert p0._cache is acv
            assert c0._cache is acv
            assert c1._cache is acv
        # now we go offline...
        with pytest.raises(aiohttp.client_exceptions.ClientConnectorError):
            p0 = await acv.obtain(Post, 1)
        # but can still operate on cached objects
        p0 = await acv.obtain(Post, 0)
        comments = await p0.comments
        assert [c.id for c in comments] == [0, 1]
        assert [c.text for c in comments] == ['comment0', 'comment1']


@pytest.mark.asyncio()
async def test_not_using_cache() -> None:
    """Test our dataclasses operation without a cache."""
    with aioresponses.aioresponses() as mocked:
        setup_mocked_data(mocked)
        # basic querying
        p0 = await Post.__obtain__(0)
        assert p0.id == 0
        assert p0.text == 'post0'
        # querying of children: by id
        c0 = await Comment.__obtain__(0)
        # querying of children: with an async getter
        comments = await p0.comments
        assert [c.id for c in comments] == [0, 1]
        assert [c.text for c in comments] == ['comment0', 'comment1']
        # identity checks: children obtained differently are different objects
        assert comments[0] is not c0
        c1 = await Comment.__obtain__(1)
        assert comments[1] is not c1
        # identity checks: parents are the *different* objects
        assert await comments[0].post is not p0
        assert await comments[1].post is not p0
        # check that the objects are not cached
        assert p0._cache is NoCache()
        assert c0._cache is NoCache()
        assert c1._cache is NoCache()
        assert comments[0]._cache is NoCache()
        assert comments[1]._cache is NoCache()
        # check doctext proxying
        assert p0.__doc__ == 'Example dataclass to represent a blog post.'
        assert Post.comments.__doc__ == (
            '[awaitable property] ' + "Blog post's comments."
        )


@pytest.mark.asyncio()
async def test_persistence(tmp_path: pathlib.Path) -> None:
    """Test reopening cache and operating offline."""
    async with asynccachedview.cache.Cache(tmp_path / 'db.sqlite') as acv:
        with aioresponses.aioresponses() as mocked:
            setup_mocked_data(mocked)
            p0 = await acv.obtain(Post, 0)
            comments = await p0.comments
            assert [c.text for c in comments] == ['comment0', 'comment1']
    async with asynccachedview.cache.Cache(tmp_path / 'db.sqlite') as acv:
        p0 = await acv.obtain(Post, 0)
        comments = await p0.comments
        assert [c.text for c in comments] == ['comment0', 'comment1']
