# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""asynccachedview core.

Data model wrapper.
"""

import dataclasses
import inspect

from aiosqlitemydataclass import primary_key

from asynccachedview._nocache import NoCache


def awaitable_property(corofunc):
    """Mark an `async def` method as an awaitable property and enable caching.

    The decorated coroutine method must take `self` as the only argument,
    and return a pickleable result
    made up of primitive values and other ACVDataclasses instances.

    Specifying setters and deleters is not supported.
    """
    return _AwaitableProperty(corofunc)


class _AwaitableProperty:
    __slots__ = ('__doc__', 'attrname', 'dataclass', 'wrapped', 'wrapper')

    def __init__(self, corofunc):
        self.dataclass = self.attrname = None  # get bound in __set_name__
        self.wrapped = corofunc
        assert inspect.iscoroutinefunction(corofunc)
        self.__doc__ = f'[awaitable property] {corofunc.__doc__}'

        async def wrapper(obj):
            assert isinstance(obj, ACVDataclass)
            cache = object.__getattribute__(obj, '_cache')
            return await cache.cached_attribute_lookup(
                obj,
                self.attrname,
                self.wrapped,
            )
            return await self.wrapped(obj)

        self.wrapper = wrapper

    def __set_name__(self, owner, name):  # on attaching to class
        self.dataclass = owner
        self.attrname = name

    def __get__(self, obj, objtype=None):  # on getattr'ing the field
        if obj is None:
            return self
        wrapper = self.wrapper.__get__(obj, obj.__class__)  # bind to object
        wrapper = wrapper()
        wrapper.__name__ = self.wrapped.__name__ + '.caching_wrapper'
        wrapper.__qualname__ = self.wrapped.__qualname__ + '.caching_wrapper'
        return wrapper


class _CacheHolder:
    """Mutable container to store cache association for dataclass instance.

    This is needed to have frozen dataclass instances associated with a cache
    after their construction. It is attached to `_cache_holder` private field.
    """

    __slots__ = ('cache',)

    def __init__(self):
        self.cache = NoCache


class ACVDataclass:
    """Purely an indicator that the class has been augmented."""

    __slots__ = ()


def dataclass(cls):
    """Define a dataclass based on a python class.

    Fields collectively acting as a primary key must be decorated as
    `id: int = dataclasses.field(metadata=primary_key())` or
    `id: int = dataclasses.field(metadata=primary_key({'more': 'metadata'}))`

    Instances of the dataclass with the same values for these keys
    are considered the same instance.

    Has a similar interface to `@dataclasses.dataclass(frozen=True)`,
    but also supports attaching objects to caches.

    A dataclass `D` must also define `async def __obtain__(*identity)`
    that acts as a constructor when you later do `cache.obtain(D, *identity)`.
    """
    # This is a regular frozen dataclass
    dcls = dataclasses.dataclass(cls, frozen=True)

    # This is the wrapper class that offers extra functionality
    @dataclasses.dataclass(frozen=True)
    class DataClass(dcls, ACVDataclass):
        # Optionally remembers the cache associated with the object
        # HACKY, mutable container in frozen dataclass
        _cache_holder: _CacheHolder = dataclasses.field(
            default_factory=_CacheHolder,
            init=False,
            repr=False,
            hash=False,
            compare=False,
        )

        @property
        def _cache(self):  # HACKY
            return self._cache_holder.cache

        def _set_cache(self, cache):  # HACKY
            # identity map should protect us from associating twice
            assert self._cache_holder.cache is NoCache
            self._cache_holder.cache = cache

    DataClass.__name__ = cls.__name__ + '.ACVDataclass'
    DataClass.__qualname__ = cls.__qualname__
    DataClass.__module__ = cls.__module__
    DataClass.__doc__ = cls.__doc__

    return DataClass


__all__ = ['dataclass', 'awaitable_property', 'primary_key']
