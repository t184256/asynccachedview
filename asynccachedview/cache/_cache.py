# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements caching objects in a database."""

import asyncio
import collections
import dataclasses
import pathlib
import typing
import weakref

import aiosqlitemydataclass

from asynccachedview._nocache import NoCache
from asynccachedview.cache._pickler import (
    pickle_and_reduce_to_identities,
    unpickle_and_reconstruct_from_identities,
)
from asynccachedview.dataclasses._core import ACVDataclass as _ACVDataclass
from asynccachedview.dataclasses._core import ACVDataclassEx as _ACVDataclassEx

if typing.TYPE_CHECKING:
    from aiosqlitemydataclass._extra_types import DataclassInstance

    from asynccachedview.cache._cache import Cache as _Cache

    _T = typing.TypeVar('_T')
    _P = typing.ParamSpec('_P')
    _T_co = typing.TypeVar('_T_co', covariant=True)

    _ACVDataclassAny: typing.TypeAlias = (
        _ACVDataclass[_P, _T_co] | _ACVDataclassEx[_P, _T_co]
    )

    # a bit of a sloppy typing, but it should suffice
    _ID = tuple[typing.Any, ...]
    _ACVDataclassAndID = tuple[type[_ACVDataclassAny[_P, _T_co]], _ID]
    _Dict_ID = dict[_ID, _ACVDataclassAny[_P, _T_co]]
    _DDict_ClassAndID = collections.defaultdict[
        type[_ACVDataclassAny[_P, _T_co]],
        _Dict_ID[_P, _T_co],
    ]
    _DDict_ClassIDAndAttrname = collections.defaultdict[
        type[_ACVDataclassAny[_P, _T_co]],
        collections.defaultdict[_ID, dict[str, _T]],
    ]


def get_cache(
    dataclass_obj: '_ACVDataclassAny[_P, _T_co]',
) -> '_Cache | NoCache':
    return dataclass_obj._cache or NoCache()  # noqa: SLF001


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


class WeakLockDict(weakref.WeakValueDictionary[typing.Hashable, asyncio.Lock]):
    def __getitem__(self, k: typing.Hashable) -> asyncio.Lock:
        try:
            return super().__getitem__(k)
        except KeyError:
            r = self[k] = asyncio.Lock()
            return r


class Cache(aiosqlitemydataclass.Database):
    """Implements an optional cache for your asynccachedview dataclasses.

    Implements the following behavior for dataclass objects:
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

    # convert into a per-class dual-cache object?
    id_map: '_DDict_ClassAndID[..., typing.Any]'
    field_map: '_DDict_ClassIDAndAttrname[..., typing.Any, typing.Any]'
    _locks: WeakLockDict

    def __init__(self, path: pathlib.Path | str | None = None) -> None:
        """Create a new Cache object.

        TODO: offline mode(s) of operation.
        """
        super().__init__(path)
        self.id_map = collections.defaultdict(dict)
        self.field_map = collections.defaultdict(
            lambda: collections.defaultdict(dict),
        )
        self._locks = WeakLockDict()

    def _id_map_by_class(
        self: typing.Self,
        desired_dataclass: 'type[_ACVDataclassAny[_P, _T_co]]',
    ) -> '_Dict_ID[_P, _T_co]':
        return typing.cast(
            '_Dict_ID[_P, _T_co]',
            self.id_map[desired_dataclass],
        )

    async def obtain(
        self,
        desired_dataclass: 'type[_ACVDataclassAny[_P, _T_co]]',
        *identity: '_P.args',
        **unused_kwargs: '_P.kwargs',
    ) -> '_T_co':
        """Obtain an instance of the desired dataclass with specified identity.

        Calls `desired_class.__obtain__(*identity)` under the hood
        caches the result and associates it with the cache.
        """
        async with self._locks[(desired_dataclass, *identity)]:
            assert not unused_kwargs  # HACKY

            try:
                obj = self._id_map_by_class(desired_dataclass)[identity]
                return typing.cast('_T_co', obj)
            except KeyError:
                pass
            try:
                obj = typing.cast(
                    '_ACVDataclassAny[_P, _T_co]',
                    await self.get(desired_dataclass, *identity),
                )
            except aiosqlitemydataclass.RecordMissingError:
                pass
            else:
                assert isinstance(obj, desired_dataclass)
                self.id_map[desired_dataclass][identity] = obj
                obj._set_cache(self)  # noqa: SLF001
                return typing.cast('_T_co', obj)
            if hasattr(desired_dataclass, '__obtain__'):
                obj = typing.cast(
                    '_ACVDataclassAny[_P, _T_co]',
                    await desired_dataclass.__obtain__(*identity),
                )
                assert isinstance(obj, _ACVDataclass)
            else:
                assert hasattr(desired_dataclass, '__obtain_ex__')
                obj = typing.cast(
                    '_ACVDataclassEx[_P, _T_co]',
                    await desired_dataclass.__obtain_ex__(self, *identity),
                )
                assert isinstance(obj, _ACVDataclassEx)
            assert obj.__class__ == desired_dataclass
            obj = await self.cache(obj, identity=identity)
            return typing.cast('_T_co', obj)

    def _obtain_mapped(
        self,
        desired_dataclass: 'type[_ACVDataclassAny[_P, _T_co]]',
        *identity: '_P.args',
        **unused_kwargs: '_P.kwargs',
    ) -> '_ACVDataclassAny[_P, _T_co]':
        assert not unused_kwargs
        return self._id_map_by_class(desired_dataclass)[identity]

    async def cache(
        self,
        obj: '_ACVDataclassAny[_P, _T_co]',
        identity: '_ID | None' = None,
    ) -> '_ACVDataclassAny[_P, _T_co]':
        """Associates an already obtained/constructed object with the cache.

        Can return another object with same identity
        if that object was associated with the cache beforehand.
        """
        _cls = obj.__class__
        if identity is None:
            assert isinstance(obj, _ACVDataclass | _ACVDataclassEx)
            identity = identity or aiosqlitemydataclass.identity(
                typing.cast('DataclassInstance', obj),
            )
        try:
            return self._id_map_by_class(_cls)[identity]
        except KeyError:
            pass
        await self.put(typing.cast('DataclassInstance', obj))
        self.id_map[_cls][identity] = obj
        obj._set_cache(self)  # noqa: SLF001
        return obj

    async def cache_attribute(
        self,
        _cls: 'type[_ACVDataclassAny[_P, _T_co]]',
        _id: '_P.args',
        attrname: str,
        res: '_T',
    ) -> None:
        async with self._locks[(_cls, _id, attrname)]:
            _id_str = str(_id)
            # pickle and collect ACVDataclassAny instances
            data, collected = pickle_and_reduce_to_identities(res)
            # associate
            for c, i in collected:
                await self.cache(c, identity=i)
            # store in db
            rec = AttrCacheRecord(
                _cls.__qualname__,
                _id_str,
                attrname,
                data,
            )
            await self.put(rec)
            # unpickle
            res = await unpickle_and_reconstruct_from_identities(data, self)
            # store mapping in ram
            self.field_map[_cls][_id][attrname] = res

    async def cached_attribute_lookup(
        self,
        obj: '_ACVDataclassAny[_P, _T_co]',
        attrname: str,
        coroutine_func: typing.Callable[
            ['_ACVDataclassAny[_P, _T_co]'],
            typing.Coroutine[typing.Any, typing.Any, '_T'],
        ],
    ) -> '_T':
        """Return cached `obj.attrname` awaitable property result.

        Tries in-memory map first, database in case of a cache miss,
        actually executes the coroutine if none of this have the answer.
        """
        async with self._locks[(obj, attrname, coroutine_func)]:
            _id = aiosqlitemydataclass.identity(
                typing.cast('DataclassInstance', obj),
            )
            try:
                field_map = typing.cast(
                    collections.defaultdict['_ID', dict[str, '_T']],
                    self.field_map[obj.__class__],
                )
                return field_map[_id][attrname]
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
                res = await coroutine_func(obj)
                # pickle and collect ACVDataclassAny instances
                data, collected = pickle_and_reduce_to_identities(res)
                # associate
                for c, i in collected:
                    await self.cache(c, identity=i)
                # store in db
                rec = AttrCacheRecord(
                    _cls.__qualname__,
                    _id_str,
                    attrname,
                    data,
                )
                await self.put(rec)
            # unpickle
            res = await unpickle_and_reconstruct_from_identities(data, self)
            # store mapping in ram
            self.field_map[obj.__class__][_id][attrname] = res
            return res
