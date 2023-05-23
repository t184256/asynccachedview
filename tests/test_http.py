# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test accessing an HTTP resource."""

import aiohttp
import aioresponses

import pytest

import asynccachedview


@asynccachedview.dataclass
class Post:
    """Example dataclass to represent a blog post."""

    id: int
    text: str

    @classmethod
    async def __obtain__(cls, id_):
        # working with session directly, intentially presenting both ways
        async with asynccachedview.sources.http.shared_session() as sess:
            async with sess.get('http://ex.ample/post',
                                params={'id': id_}) as resp:
                assert resp.status == 200
                j = await resp.json()
                assert j['id'] == id_
                return cls(id_, j['text'])

    @property
    async def comments(self):
        """Blog post's comments."""
        url = 'http://ex.ample/comments'
        # shorter version, intentionally presenting both ways
        async with asynccachedview.sources.http.json(url,
                                                     post_id=self.id) as j:
            return tuple(Comment(id=c['id'], post_id=self.id, text=c['text'])
                         for c in j)


@asynccachedview.dataclass(identity=('id',))  # this is the default
class Comment:
    """Example dataclass to represent a blog post's comment."""

    id: int
    post_id: int
    text: str

    @classmethod
    async def __obtain__(cls, id_):
        url = 'http://ex.ample/comment'
        async with asynccachedview.sources.http.json(url, id=id_) as j:
            assert j['id'] == id_
            return cls(id_, j['post_id'], j['text'])

    @property
    async def post(self):
        """Parent post."""
        return await Post.__obtain__(self.post_id)


def setup_mocked_data(mocked):
    """Configure `aioresponses.aioresponses()` to output example data."""
    mocked.get('http://ex.ample/post?id=0', status=200,
               payload={'id': 0, 'text': 'post0'},
               repeat=True)
    mocked.get('http://ex.ample/comments?post_id=0', status=200,
               payload=[{'id': 0, 'post_id': 0, 'text': 'comment0'},
                        {'id': 1, 'post_id': 0, 'text': 'comment1'}],
               repeat=True)
    mocked.get('http://ex.ample/comment?id=0', status=200,
               payload={'id': 0, 'post_id': 0, 'text': 'comment0'},
               repeat=True)
    mocked.get('http://ex.ample/comment?id=1', status=200,
               payload={'id': 1, 'post_id': 0, 'text': 'comment1'},
               repeat=True)


@pytest.mark.asyncio
async def test_using_cache() -> None:
    """Test our dataclasses operation with a cache."""
    async with asynccachedview.Cache() as acv:
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
            assert await(comments[0].post) is p0
            assert await(comments[1].post) is p0
            # check that all the objects are cached (TODO: check offline)
            assert p0._cache is acv  # pylint: disable=protected-access
            assert c0._cache is acv  # pylint: disable=protected-access
            assert c1._cache is acv  # pylint: disable=protected-access
        # now we go offline...
        with pytest.raises(aiohttp.client_exceptions.ClientConnectorError):
            p0 = await acv.obtain(Post, 1)
        # but can still operate on cached objects
        p0 = await acv.obtain(Post, 0)
        comments = await p0.comments
        assert [c.id for c in comments] == [0, 1]
        assert [c.text for c in comments] == ['comment0', 'comment1']


@pytest.mark.asyncio
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
        # identity checks: children obtained differently are *different* objects
        assert comments[0] is not c0
        c1 = await Comment.__obtain__(1)
        assert comments[1] is not c1
        # identity checks: parents are the *different* objects
        assert await(comments[0].post) is not p0
        assert await(comments[1].post) is not p0
        # check that the objects are not cached
        assert p0._cache is None  # pylint: disable=protected-access
        assert c0._cache is None  # pylint: disable=protected-access
        assert c1._cache is None  # pylint: disable=protected-access
        assert comments[0]._cache is None  # pylint: disable=protected-access
        assert comments[1]._cache is None  # pylint: disable=protected-access
