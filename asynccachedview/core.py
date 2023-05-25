# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""
asynccachedview core.

Data model wrapper.
"""

import dataclasses
import inspect
import functools


def awaitable_property(corofunc):
    """
    Mark an `async def` method as an awaitable property and enable caching.

    The decorated coroutine method must take `self` as the only argument:
    `async def somename(self):`.
    Specifying setters and deleters is not supported.
    """
    assert inspect.iscoroutinefunction(corofunc)
    attrname = corofunc.__name__

    @functools.wraps(corofunc)
    async def wrapping_coroutine(self):
        cache = object.__getattribute__(self, '_cache')
        assert isinstance(self, ACVDataclass)
        if cache is not None:
            try:
                return cache.cached_attribute(self, attrname)
            except KeyError:
                pass
        print(f'awaiting {corofunc=}')
        results = await corofunc(self)
        print(f'awaited {corofunc=}')
        if cache is not None:
            results = cache.associate_attribute(self, attrname, results)
        return results
    wrapping_coroutine.__name__ = corofunc.__name__ + '.caching_wrapper'
    wrapping_coroutine.__qualname__ = (corofunc.__qualname__ +
                                       '.caching_wrapper')
    wrapping_coroutine.__doc__ = f'[awaitable property] {corofunc.__doc__}'
    prop = property(wrapping_coroutine)
    return prop


class _CacheHolder:
    """
    Small mutable container to store cache associated with dataclass instance.

    This is needed to have frozen dataclass instances associated with a cache
    after their construction. It is attached to `_cache_holder` private field.
    """

    __slots__ = ('cache',)

    def __init__(self):
        self.cache = None


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
        for fname in identity_field_names:
            assert any(field.name == fname for field in fields)

        # This is the wrapper class that offers extra functionality
        @dataclasses.dataclass(frozen=True)
        # pylint: disable-next=missing-class-docstring
        class DataClass(dcls, ACVDataclass):
            # Knows which fields are the identity (primary key)
            _identity_field_names = identity_field_names

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


__all__ = ['dataclass']
