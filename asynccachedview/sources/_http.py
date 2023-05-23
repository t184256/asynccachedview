# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""HTTP data source of asynccachedview, provides a shared session."""

import asyncio
import contextlib

import aiohttp


_shared_session = None


@contextlib.asynccontextmanager
async def shared_session():
    global _shared_session
    if _shared_session is None:
        _shared_session = await aiohttp.ClientSession().__aenter__()

        loop = asyncio.get_running_loop()
        original_close = loop.close

        async def close_shared_session():
            global _shared_session
            await _shared_session.__aexit__(None, None, None)

        def extended_close():
            global _shared_session
            if _shared_session is not None:
                loop.run_until_complete(close_shared_session())
            _shared_session = None
            return original_close()

        loop.close = extended_close
    yield _shared_session


@contextlib.asynccontextmanager
async def json(url, **params):
    async with shared_session() as sess:
        async with sess.get(url, params=params) as resp:
            assert resp.status == 200
            yield await resp.json()
