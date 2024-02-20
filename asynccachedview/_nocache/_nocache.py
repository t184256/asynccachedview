# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements a NoCache non-caching stub."""

import typing

if typing.TYPE_CHECKING:
    from asynccachedview.dataclasses._core import ACVDataclass, ACVDataclassEx

    _T = typing.TypeVar('_T')
    _T_co = typing.TypeVar('_T_co', covariant=True)
    _P = typing.ParamSpec('_P')
    _ID = tuple[typing.Any, ...]

    _ACVDataclassAny: typing.TypeAlias = (
        ACVDataclass[_P, _T_co] | ACVDataclassEx[_P, _T_co]
    )


class NoCache:
    slots = ('_instance',)

    _instance: typing.ClassVar[typing.Self | None] = None

    def __new__(cls) -> typing.Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return typing.cast(typing.Self, cls._instance)

    @classmethod
    async def obtain(
        cls,
        dataclass: 'type[_ACVDataclassAny[_P, _T_co]]',
        *identity: '_P.args',
        **unused_kwargs: '_P.kwargs',
    ) -> '_T_co':
        assert not unused_kwargs
        if hasattr(dataclass, '__obtain__'):
            r = await dataclass.__obtain__(*identity)
        else:
            assert hasattr(dataclass, '__obtain_ex__')
            r = await dataclass.__obtain_ex__(cls(), *identity)
        return typing.cast('_T_co', r)

    @staticmethod
    async def cache(
        obj: '_ACVDataclassAny[_P, _T_co]',
        identity: '_ID | None' = None,  # noqa: ARG004
    ) -> '_ACVDataclassAny[_P, _T_co]':
        return obj

    @staticmethod
    async def cache_attribute(
        _cls: 'type[_ACVDataclassAny[_P, _T_co]]',
        _id: '_P.args',
        attrname: str,
        res: '_T',
    ) -> None:
        pass

    @staticmethod
    async def cached_attribute_lookup(
        obj: '_ACVDataclassAny[_P, _T_co]',
        _unused_attrname: str,
        coroutine: typing.Callable[
            ['_ACVDataclassAny[_P, _T_co]'],
            typing.Coroutine[typing.Any, typing.Any, '_T'],
        ],
    ) -> '_T':
        return await coroutine(obj)


__all__ = ['NoCache']
