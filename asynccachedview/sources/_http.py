# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""HTTP data source of asynccachedview, provides a shared session."""

import asyncio
import contextlib
import http

import aiohttp

_shared_session = None
_lock = asyncio.Lock()


async def _shared_session_init():
    # TODO: abstract out hooking into loop close
    global _shared_session  # noqa: PLW0603
    _shared_session = await aiohttp.ClientSession().__aenter__()

    loop = asyncio.get_running_loop()
    original_close = loop.close

    def extended_close():
        async def close_shared_session():
            async with _lock:
                global _shared_session  # noqa: PLW0603
                assert _shared_session is not None
                await _shared_session.__aexit__(None, None, None)
                _shared_session = None

        if _shared_session is not None:
            loop.run_until_complete(close_shared_session())
        return original_close()

    loop.close = extended_close
    return _shared_session


@contextlib.asynccontextmanager
async def shared_session():
    """Create a shared `aiohttp.ClientSession`, cleaned up with event loop."""
    global _shared_session  # noqa: PLW0603
    async with _lock:
        if _shared_session is None:
            _shared_session = await _shared_session_init()
        pass  # noqa: PIE790; coverage needs that
    yield _shared_session


@contextlib.asynccontextmanager
async def json(url, **params):
    """Fetch JSON from URL using shared session, asserting HTTP status 200."""
    async with shared_session() as sess, sess.get(url, params=params) as resp:
        assert resp.status == http.HTTPStatus.OK
        yield await resp.json()
