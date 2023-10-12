# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements a NoCache non-caching stub."""


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
        return await coroutine(obj)
