# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements a NoCache non-caching stub."""

from asynccachedview.dataclasses._restrictions import inspect_return_type


class NoCache:
    @staticmethod
    async def obtain(dataclass, *identity):
        ret = await dataclass.__obtain__(*identity)
        assert isinstance(ret, dataclass)
        return ret

    @staticmethod
    async def cache(x):
        pass

    @staticmethod
    async def cached_attribute_lookup(obj, _unused_attrname, coroutine):
        inspect_return_type(coroutine)
        res = await coroutine(obj)
        if isinstance(res, list):
            msg = 'return a tuple, not a list'
            raise TypeError(msg)
        return res
