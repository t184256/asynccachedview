# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""
asynccachedview core.

Data model wrapper.
"""

import dataclasses
import inspect


class CacheHolder:
    __slots__ = 'cache'
    def __init__(self):
        self.cache = None


class ACVDataclass:
    """Purely an indicator that the class has been augmented."""
    __slots__ = []


def dataclass(cls=None, /, *, identity='id'):
    if isinstance(identity, str):
        identity = (identity,)
    identity_field_names = identity

    def augment(cls):
        # Main function that upgrades the dataclass with caching
        dcls = dataclasses.dataclass(cls, frozen=True)
        fields = dataclasses.fields(dcls)

        # This is the wrapper class that offers extra functionality
        @dataclasses.dataclass(frozen=True)
        class DataClass(dcls, ACVDataclass):
            # Knows which fields are the identity (primary key)
            _identity_field_names = identity_field_names

            @property
            def _identity(self):
                return tuple(getattr(self, fname)
                             for fname in self._identity_field_names)

            # Optionally remembers the cache associated with the object
            # HACKY, mutable container in frozen dataclass
            _cache_holder: CacheHolder = \
                dataclasses.field(default_factory=CacheHolder)

            @property
            def _cache(self):  # HACKY
                return self._cache_holder.cache

            def _set_cache(self, cache):  # HACKY
                if self._cache_holder.cache is None:
                    self._cache_holder.cache = cache

            # And wraps the other objects produced from this one:
            def __getattribute__(self, key):
                r = object.__getattribute__(self, key)
                if key.startswith('_'):
                    return r
                if isinstance(r, ACVDataclass):
                    # An object's field is another object.
                    cache = object.__getattribute__(self, '_cache')
                    return cache.associate(self, r)
                elif inspect.iscoroutine(r):
                    print(f'wrapping coroutine {r}, self={self}')

                    async def wrapping_coroutine():
                        cache = object.__getattribute__(self, '_cache')
                        if cache is not None:
                            try:
                                print('TRY')
                                cached = cache.cached_attribute(self, key)
                                r.close()
                                return cached
                            except KeyError:
                                pass
                            print('MISS')
                        print(f'awaiting {r=}')
                        results = await r
                        print(f'awaited {r=}')
                        if cache is not None:
                            results = cache.associate_attribute(self,
                                                                key, results)
                        return results
                    wrapping_coroutine.__name__ = (r.__name__ +
                                                   '.caching_wrapper')
                    wrapping_coroutine.__qualname__ = (r.__qualname__  +
                                                       '.caching_wrapper')
                    return wrapping_coroutine()
                return r
        DataClass.__name__ = cls.__name__ + '.DataClass'
        DataClass.__qualname__ = cls.__qualname__ + '.DataClass'
        DataClass.__module__ = cls.__module__

        return DataClass

    if cls is None:
        return augment  # called with arguments
    return augment(cls)  # called without arguments


__all__ = ['dataclass']
