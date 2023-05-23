# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements caching objects in a database."""

import types
import typing
import collections

import asynccachedview.core


class Cache:
    def __init__(self):
        self.id_map = collections.defaultdict(dict)
        self.field_map = collections.defaultdict(lambda:
                                                 collections.defaultdict(dict))

    async def __aenter__(self) -> typing.Self:
        return self

    async def __aexit__(self,
                        _exc_type: typing.Optional[type[BaseException]],
                        _exc_val: typing.Optional[BaseException],
                        _exc_tb: typing.Optional[types.TracebackType]
                        ) -> None:
        pass

    async def obtain(self, desired_class, id):
        print('quer', desired_class, id)
        try:
            return self.id_map[desired_class][id]
        except KeyError:
            print('miss', desired_class, id)
            return self._associate_single(await desired_class.__obtain__(id))

    def _associate_single(self, obj):
        """
        Associates an object with the cache.

        Can return another object with same identity
        if that object was associated with the cache first.
        """
        assert isinstance(obj, asynccachedview.core.ACVDataclass)
        try:
            return self.id_map[obj.__class__][obj.id]
        except KeyError:
            self.id_map[obj.__class__][obj.id] = obj
        obj._set_cache(self)
        return obj

    def associate(self, x):
        """
        Associates an object or a container of them with the cache.

        Can return different objects with same identity
        if these objects were associated with the cache first.
        """
        if isinstance(x, tuple):
            return tuple(self._associate_single(e) for e in x)
        if isinstance(x, list):
            return [self._associate_single(e) for e in x]
        return self._associate_single(x)

    def associate_attribute(self, obj, attrname, attrval):
        # for awaitable attrs only, rename?
        print('ASSOCIATING AWAITABLE ATTRIBUTE', obj, attrname)
        try:
            return self.field_map[obj.__class__][obj.id][attrname]
        except KeyError:
            print('MISS')
            attrval = self.associate(attrval)
            self.field_map[obj.__class__][obj.id][attrname] = attrval
            return attrval

    def cached_attribute(self, obj, attrname):
        # for awaitable attrs only, rename?
        return self.field_map[obj.__class__][obj.id][attrname]
