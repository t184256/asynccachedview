# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""asynccachedview core.

Data model wrapper.
"""

import dataclasses
import typing

import awaitable_property as lib_awp
from aiosqlitemydataclass import primary_key

from asynccachedview._nocache import NoCache
from asynccachedview.dataclasses._obtainable import Obtainable, ObtainableEx

if typing.TYPE_CHECKING:
    from asynccachedview.cache._cache import Cache

_P = typing.ParamSpec('_P')
_T_co = typing.TypeVar('_T_co', covariant=True)
_T_obj = typing.TypeVar('_T_obj')


class _CacheHolder:
    """Mutable container to store cache association for dataclass instance.

    This is needed to have frozen dataclass instances associated with a cache
    after their construction. It is attached to `_cache_holder` private field.
    """

    __slots__ = ('cache',)

    def __init__(self) -> None:
        self.cache: 'Cache | NoCache' = NoCache()


@dataclasses.dataclass(frozen=True)
class ACVDataclassBase:
    """Inherit from for your custom dataclasses from it to make them cacheable.

    ```
    @dataclasses.dataclass(frozen=True)
    class Record(ACVDataclass[[int], 'Record']):
        id: int = dataclasses.field(metadata=primary_key())
        str: s

        @classmethod
        async def __obtain__(cls, i: int) -> Self:
            return Record(i, await db.select_by_id(i))
    ```
    """

    slots = ('_cache_holder',)

    _cache_holder: _CacheHolder = dataclasses.field(
        default_factory=_CacheHolder,
        init=False,
        repr=False,
        hash=False,
        compare=False,
    )

    @property
    def _cache(self) -> 'Cache | NoCache':  # HACKY
        return self._cache_holder.cache

    def _set_cache(self: typing.Self, cache: 'Cache') -> None:
        # identity map should protect us from associating twice
        assert self._cache_holder.cache is NoCache()
        self._cache_holder.cache = cache


class ACVDataclass(ACVDataclassBase, Obtainable[_P, _T_co]):
    pass


class ACVDataclassEx(ACVDataclassBase, ObtainableEx[_P, _T_co]):
    pass


###


_T_val = typing.TypeVar('_T_val')


async def cache_property_access(
    obj: ACVDataclass[_P, _T_co] | ACVDataclassEx[_P, _T_co],
    corofunc: typing.Callable[
        [ACVDataclass[_P, _T_co] | ACVDataclassEx[_P, _T_co]],
        typing.Coroutine[typing.Any, typing.Any, _T_val],
    ],
    attrname: str,
) -> _T_val:
    """Hooks into the property fetching process and performs caching."""
    assert isinstance(obj, ACVDataclass | ACVDataclassEx)
    cache = obj._cache  # noqa: SLF001
    return await cache.cached_attribute_lookup(obj, attrname, corofunc)


def awaitable_property(
    corofunc: typing.Callable[
        [_T_obj],
        typing.Coroutine[typing.Any, typing.Any, _T_val],
    ],
) -> 'lib_awp.AwaitableProperty[_T_obj, _T_val, _T_val]':
    """Mark an `async def` method as an awaitable property and enable caching.

    The decorated coroutine method must take `self` as the only argument,
    and return a pickleable result
    made up of primitive values and other ACVDataclasses instances.

    Specifying setters and deleters is not supported.
    """
    # Awkwardness ensues: https://github.com/python/typing/issues/548
    # The function is basically just
    # `return awaitable_property(transform=cache_property_access)(corofunc)`
    # but it's also where we hide our homegrown kinds from the users.

    # We know we can always cast _T_obj to ACVDataclass(Ex)[_P, _T_obj]
    corofunc_ = typing.cast(
        typing.Callable[
            [ACVDataclass[..., _T_obj] | ACVDataclassEx[..., _T_obj]],
            typing.Coroutine[typing.Any, typing.Any, _T_val],
        ],
        corofunc,
    )

    cacher = lib_awp.awaitable_property(transform=cache_property_access)
    prop = cacher(corofunc_)

    # ... and, vice versa, ACVDataclass(Ex)[_P, _T_obj] to _T_obj
    return typing.cast(
        'lib_awp.AwaitableProperty[_T_obj, _T_val, _T_val]',
        prop,
    )


__all__ = ['ACVDataclass', 'awaitable_property', 'primary_key']
