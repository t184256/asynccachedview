# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""HTTP data source of asynccachedview, provides a shared session."""

import asyncio
import contextlib

import aiohttp


_shared_session = None  # pylint: disable=invalid-name
_lock = asyncio.Lock()  # pylint: disable=invalid-name


@contextlib.asynccontextmanager
async def shared_session():
    """Create a shared `aiohttp.ClientSession`, cleaned up with event loop."""
    global _shared_session  # pylint: disable=invalid-name,global-statement
    async with _lock:
        if _shared_session is None:
            # pylint: disable-next=unnecessary-dunder-call
            _shared_session = await aiohttp.ClientSession().__aenter__()

            loop = asyncio.get_running_loop()
            original_close = loop.close

            def extended_close():
                async def close_shared_session():
                    async with _lock:
                        # pylint: disable-next=invalid-name,global-statement
                        global _shared_session
                        assert _shared_session is not None
                        await _shared_session.__aexit__(None, None, None)
                        _shared_session = None

                # pylint: disable-next=invalid-name,global-statement
                if _shared_session is not None:
                    loop.run_until_complete(close_shared_session())
                return original_close()

            loop.close = extended_close
    yield _shared_session


@contextlib.asynccontextmanager
async def json(url, **params):
    """Fetch JSON from URL using shared session, asserting HTTP status 200."""
    async with shared_session() as sess:
        async with sess.get(url, params=params) as resp:
            assert resp.status == 200
            yield await resp.json()
