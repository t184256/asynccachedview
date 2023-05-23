# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""
asynccachedview core.

Data model wrapper.
"""

import dataclasses
import inspect
import functools


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

    __slots__ = []


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
                dataclasses.field(default_factory=_CacheHolder)

            @property
            def _cache(self):  # HACKY
                return self._cache_holder.cache

            def _set_cache(self, cache):  # HACKY
                if self._cache_holder.cache is None:
                    self._cache_holder.cache = cache

            def _wrap_awaitable_property(self, awaitable, attrname):
                @functools.wraps(awaitable)
                async def wrapping_coroutine():
                    cache = object.__getattribute__(self, '_cache')
                    if cache is not None:
                        try:
                            print('TRY')
                            cached = cache.cached_attribute(self, attrname)
                            awaitable.close()
                            return cached
                        except KeyError:
                            pass
                        print('MISS')
                    print(f'awaiting {awaitable=}')
                    results = await awaitable
                    print(f'awaited {awaitable=}')
                    if cache is not None:
                        results = cache.associate_attribute(self,
                                                            attrname, results)
                    return results
                wrapping_coroutine.__name__ = (awaitable.__name__ +
                                               '.caching_wrapper')
                wrapping_coroutine.__qualname__ = (awaitable.__qualname__ +
                                                   '.caching_wrapper')
                return wrapping_coroutine()

            # And wraps the other objects produced from this one:
            def __getattribute__(self, attrname):
                attr = object.__getattribute__(self, attrname)
                if attrname.startswith('_'):
                    return attr
                if isinstance(attr, ACVDataclass):
                    # An object's field is another object.
                    cache = object.__getattribute__(self, '_cache')
                    return cache.associate(self, attr)
                if inspect.iscoroutine(attr):
                    print(f'wrapping coroutine {attr}, self={self}')
                    return self._wrap_awaitable_property(attr, attrname)
                return attr
        DataClass.__name__ = cls.__name__ + '.DataClass'
        DataClass.__qualname__ = cls.__qualname__ + '.DataClass'
        DataClass.__module__ = cls.__module__
        DataClass.__doc__ = cls.__doc__

        for attrname in dir(cls):
            if not attrname.startswith('_'):
                attr = getattr(cls, attrname)
                if isinstance(attr, property):
                    getattr(DataClass, attrname).__doc__ = (
                        f'[awaitable property] {attr.__doc__}'
                    )

        return DataClass

    if cls is None:
        return augment  # called with arguments
    return augment(cls)  # called without arguments


__all__ = ['dataclass']
