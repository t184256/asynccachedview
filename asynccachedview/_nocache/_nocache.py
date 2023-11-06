# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements a NoCache non-caching stub."""

import typing

if typing.TYPE_CHECKING:
    from asynccachedview.dataclasses._core import ACVDataclass

    _T = typing.TypeVar('_T')
    _T_co = typing.TypeVar('_T_co', covariant=True)
    _P = typing.ParamSpec('_P')
    _ID = tuple[typing.Any, ...]


class NoCache:
    slots = ('_instance',)

    _instance: typing.ClassVar[typing.Self | None] = None

    def __new__(cls) -> typing.Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return typing.cast(typing.Self, cls._instance)

    @staticmethod
    async def obtain(
        dataclass: 'type[ACVDataclass[_P, _T_co]]',
        *identity: '_P.args',
        **unused_kwargs: '_P.kwargs',
    ) -> '_T_co':
        assert not unused_kwargs
        return typing.cast('_T_co', await dataclass.__obtain__(*identity))

    @staticmethod
    async def cache(
        obj: 'ACVDataclass[_P, _T_co]',
        identity: '_ID | None' = None,  # noqa: ARG004
    ) -> 'ACVDataclass[_P, _T_co]':
        return obj

    @staticmethod
    async def cached_attribute_lookup(
        obj: 'ACVDataclass[_P, _T_co]',
        _unused_attrname: str,
        coroutine: typing.Callable[
            ['ACVDataclass[_P, _T_co]'],
            typing.Coroutine[typing.Any, typing.Any, '_T'],
        ],
    ) -> '_T':
        return await coroutine(obj)


__all__ = ['NoCache']
