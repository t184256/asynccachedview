# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""
asynccachedview core.

Data model wrapper.
"""

import dataclasses
import inspect


def awaitable_property(corofunc):
    """
    Mark an `async def` method as an awaitable property and enable caching.

    The decorated coroutine method must take `self` as the only argument:
    `async def somename(self):`.
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
            if cache is not None:
                try:
                    return cache.cached_attribute(obj, self.attrname)
                except KeyError:
                    pass
            print(f'awaiting {self.wrapped=}')
            results = await self.wrapped(obj)
            print(f'awaited {self.wrapped=}')
            if cache is not None:
                results = cache.associate_attribute(obj,
                                                    self.attrname, results)
            return results
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
    """
    Small mutable container to store cache associated with dataclass instance.

    This is needed to have frozen dataclass instances associated with a cache
    after their construction. It is attached to `_cache_holder` private field.
    """

    __slots__ = ('cache',)

    def __init__(self):
        self.cache = None


async def obtain_related(dataclass_instance, desired_dataclass, *identity):
    """Obtain an object + associate it with cache of existing instance."""
    # pylint: disable-next=protected-access
    cache = dataclass_instance._cache_holder.cache
    if cache is not None:
        return await cache.obtain(desired_dataclass, *identity)
    return await desired_dataclass.__obtain__(*identity)


async def associate_related(dataclass_instance, x):
    """Associate dataclass instance(s) with cache of existing instance."""
    # pylint: disable-next=protected-access
    cache = dataclass_instance._cache_holder.cache
    if cache is not None:
        return cache.associate(x)


class ACVDataclass:
    """Purely an indicator that the class has been augmented."""

    __slots__ = ()


def dataclass(cls=None, /, *, identity='id'):  # noqa: no-mccabe
    """
    Define a dataclass based on a python class.

    `identity` is an attribute name or a tuple of them
    that define the "primary key" of the dataclass.
    Instances of the dataclass with the same values for these keys
    are considered the same instance. Defaults to `'id'`.

    Has a similar interface to `@dataclasses.dataclass(frozen=True)`,
    but also supports attaching objects to caches.

    A dataclass `D` must define `async def __obtain__(*identity)`
    that acts as a constructor when you later do `cache.obtain(D, *identity)`.
    """
    if isinstance(identity, str):
        identity = (identity,)
    identity_field_names = identity

    def augment(cls):
        # Main function that upgrades the dataclass with caching
        dcls = dataclasses.dataclass(cls, frozen=True)
        fields = dataclasses.fields(dcls)
        all_field_names = tuple(f.name
                                for f in fields if f.name != '_cache_holder')
        for fname in identity_field_names:
            assert all(fname in all_field_names for field in fields)

        # This is the wrapper class that offers extra functionality
        @dataclasses.dataclass(frozen=True)
        # pylint: disable-next=missing-class-docstring
        class DataClass(dcls, ACVDataclass):
            # Knows which fields are the identity (primary key)
            _identity_field_names = identity_field_names
            _all_field_names = all_field_names

            @property
            def _identity(self):
                return tuple(getattr(self, fname)
                             for fname in self._identity_field_names)

            # Optionally remembers the cache associated with the object
            # HACKY, mutable container in frozen dataclass
            _cache_holder: _CacheHolder = \
                dataclasses.field(default_factory=_CacheHolder,
                                  init=False, repr=False,
                                  hash=False, compare=False, kw_only=True)

            @property
            def _cache(self):  # HACKY
                return self._cache_holder.cache

            def _set_cache(self, cache):  # HACKY
                # identity map should protect us from associating twice
                assert self._cache_holder.cache is None
                self._cache_holder.cache = cache

        DataClass.__name__ = cls.__name__ + '.DataClass'
        DataClass.__qualname__ = cls.__qualname__ + '.DataClass'
        DataClass.__module__ = cls.__module__
        DataClass.__doc__ = cls.__doc__

        return DataClass

    if cls is None:
        return augment  # called with arguments
    return augment(cls)  # called without arguments


__all__ = ['dataclass', 'awaitable_property',
           'obtain_related', 'associate_related']
