# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements caching objects in a database."""

import collections
import types
import typing

import aiosqlitemydataclass

import asynccachedview.dataclasses._core


class Cache:
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

    def __init__(self):
        """Create a new Cache object.

        TODO: offline mode(s) of operation.
        """
        self.id_map = collections.defaultdict(dict)
        self.field_map = collections.defaultdict(
            lambda: collections.defaultdict(dict),
        )

    async def __aenter__(self) -> typing.Self:
        return self

    async def __aexit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: types.TracebackType | None,
    ) -> None:
        pass

    async def obtain(self, desired_dataclass, *identity):
        """Obtain an instance of the desired dataclass with specified identity.

        Calls `desired_class.__obtain__(*identity)` under the hood
        caches the result and associates it with the cache.
        """
        try:
            return self.id_map[desired_dataclass][identity]
        except KeyError:
            return self._associate_single(
                await desired_dataclass.__obtain__(*identity),
            )

    def _associate_single(self, obj):
        """Associates an already obtained/constructed object with the cache.

        Can return another object with same identity
        if that object was associated with the cache beforehand.
        """
        _core = asynccachedview.dataclasses._core  # noqa: SLF001
        assert isinstance(obj, _core.ACVDataclass)
        _cls = obj.__class__
        _id = aiosqlitemydataclass.identity(obj)
        try:
            return self.id_map[_cls][_id]
        except KeyError:
            self.id_map[_cls][_id] = obj
        obj._set_cache(self)  # noqa: SLF001
        return obj

    def associate(self, x):
        """Associates one or more existing dataclass instances with the cache.

        `x` might be a single object or a tuple of them.
        Can return different objects with same identity
        if these objects were associated with the cache beforehand.
        """
        if isinstance(x, tuple):
            return tuple(self._associate_single(e) for e in x)
        if isinstance(x, list):
            msg = 'return a tuple, not a list'
            raise TypeError(msg)
        return self._associate_single(x)

    def associate_attribute(self, obj, attrname, attrval):
        """Cache and associate `obj.attrname` awaitable property results.

        Used for caching results of dataclasses' awaitable properties.
        """
        try:
            return self.field_map[obj.__class__][obj.id][attrname]
        except KeyError:
            attrval = self.associate(attrval)
            self.field_map[obj.__class__][obj.id][attrname] = attrval
            return attrval

    def cached_attribute(self, obj, attrname):
        """Return cached `obj.attrname` awaitable property results.

        Used for caching results of dataclasess' awaitable properties.
        """
        return self.field_map[obj.__class__][obj.id][attrname]
