# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements caching objects in a database."""

import collections
import dataclasses

import aiosqlitemydataclass

import asynccachedview.dataclasses._core
from asynccachedview._nocache import NoCache
from asynccachedview.cache._pickler import (
    pickle_and_reduce_to_identities,
    unpickle_and_reconstruct_from_identities,
)

_ACVDataclass = asynccachedview.dataclasses._core.ACVDataclass  # noqa: SLF001


def get_cache(dataclass_obj):
    return dataclass_obj._cache or NoCache  # noqa: SLF001


@dataclasses.dataclass(frozen=True)
class AttrCacheRecord:
    """A cached form of an attribute lookup."""

    obj_cls: str = dataclasses.field(
        metadata=aiosqlitemydataclass.primary_key(),
    )
    obj_id: str = dataclasses.field(
        metadata=aiosqlitemydataclass.primary_key(),
    )
    attrname: str = dataclasses.field(
        metadata=aiosqlitemydataclass.primary_key(),
    )
    data: bytes


class Cache(aiosqlitemydataclass.Database):
    """Implements an optional cache for your asynccachedview dataclasses.

    Implements the following behaviour for dataclass objects:
    * associates objects created through it with a cache,
      objects accessed through them also associate them with a cache
    * preserves object identity,
      returning you the same object when the identity matches
    * caches objects when constructed by identity,
      allowing to access them offline later (not implemented yet)
    * caches objects object's awaitable properties return,
      so that they also can be used offline later (not implemented yet)

    Example:
    -------
    ```
    with asynccachedview.Cache() as acv:
        o = acv.obtain(MyClass, 1)  # caches it
        c = await o.children  # caches the children objects as well
    ```
    """

    def __init__(self, path=None):
        """Create a new Cache object.

        TODO: offline mode(s) of operation.
        """
        super().__init__(path)
        self.id_map = collections.defaultdict(dict)
        self.field_map = collections.defaultdict(
            lambda: collections.defaultdict(dict),
        )

    async def obtain(self, desired_dataclass, *identity):
        """Obtain an instance of the desired dataclass with specified identity.

        Calls `desired_class.__obtain__(*identity)` under the hood
        caches the result and associates it with the cache.
        """
        try:
            return self.id_map[desired_dataclass][identity]
        except KeyError:
            pass
        try:
            obj = await self.get(desired_dataclass, *identity)
        except aiosqlitemydataclass.RecordMissingError:
            pass
        else:
            assert isinstance(obj, desired_dataclass)
            self.id_map[desired_dataclass][identity] = obj
            obj._set_cache(self)  # noqa: SLF001
            return obj
        obj = await desired_dataclass.__obtain__(*identity)
        assert isinstance(obj, _ACVDataclass)
        assert obj.__class__ == desired_dataclass
        return await self.cache(obj, identity=identity)

    def _obtain_mapped(self, desired_dataclass, *identity):
        return self.id_map[desired_dataclass][identity]

    async def cache(self, obj, identity=None):
        """Associates an already obtained/constructed object with the cache.

        Can return another object with same identity
        if that object was associated with the cache beforehand.
        """
        _cls = obj.__class__
        if identity is None:
            assert isinstance(obj, _ACVDataclass)
            identity = identity or aiosqlitemydataclass.identity(obj)
        try:
            return self.id_map[_cls][identity]
        except KeyError:
            pass
        await self.put(obj)
        self.id_map[_cls][identity] = obj
        obj._set_cache(self)  # noqa: SLF001
        return obj

    async def cached_attribute_lookup(self, obj, attrname, coroutine):
        """Return cached `obj.attrname` awaitable property result.

        Tries in-memory map first, database in case of a cache miss,
        actually executes the coroutine if none of this have the answer.
        """
        _id = aiosqlitemydataclass.identity(obj)
        try:
            return self.field_map[obj.__class__][_id][attrname]
        except KeyError:
            pass
        # not in cache, trying db
        _cls = obj.__class__
        _id_str = str(_id)
        in_db = True
        try:
            rec = await self.get(
                AttrCacheRecord,
                _cls.__qualname__,
                _id_str,
                attrname,
            )
            data = rec.data
        except aiosqlitemydataclass.RecordMissingError:
            in_db = False  # I don't want long tracebacks
        if not in_db:
            # actually calculate it
            res = await coroutine(obj)
            # pickle
            data = pickle_and_reduce_to_identities(res)
            # store in db
            rec = AttrCacheRecord(_cls.__qualname__, _id_str, attrname, data)
            await self.put(rec)
        # unpickle and associate with cache
        res = await unpickle_and_reconstruct_from_identities(data, self)
        # store mapping in ram
        self.field_map[obj.__class__][_id][attrname] = res
        return res
