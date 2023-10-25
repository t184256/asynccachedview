# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements pickling ACVDataclasses to identities and back."""

import io
import os
import pickle
import typing

import aiosqlitemydataclass

from asynccachedview.dataclasses._core import ACVDataclass

_P = typing.ParamSpec('_P')
_T_co = typing.TypeVar('_T_co', covariant=True)
# a bit of a sloppy typing, but it should suffice
_ID = tuple[typing.Any, ...]

if typing.TYPE_CHECKING:
    from aiosqlitemydataclass._extra_types import DataclassInstance

    from asynccachedview.cache._cache import Cache

    ACVDataclassAndID = tuple[type[ACVDataclass[_P, _T_co]], _ID]


class DissociatingPickler(pickle.Pickler):
    @staticmethod
    # should it be any more specific? would it be of any use?
    def persistent_id(
        obj: typing.Any,
    ) -> 'ACVDataclassAndID[_P, _T_co] | None':
        if isinstance(obj, ACVDataclass):
            obj_ = typing.cast('DataclassInstance', obj)
            return obj.__class__, aiosqlitemydataclass.identity(obj_)
        return None


def pickle_and_reduce_to_identities(obj: typing.Any) -> bytes:
    f = io.BytesIO()
    DissociatingPickler(f).dump(obj)
    return f.getvalue()


async def unpickle_and_reconstruct_from_identities(
    b: bytes,
    cache: 'Cache',
) -> typing.Any:
    f = io.BytesIO(b)

    # Pass 1: gather the objects we need to associate/cache (sync)
    collected: 'list[ACVDataclassAndID[..., typing.Any]]' = []

    class CollectingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(pid: 'ACVDataclassAndID[..., typing.Any]') -> None:
            cls, id_ = pid
            assert issubclass(cls, ACVDataclass)
            collected.append((cls, id_))

    CollectingUnpickler(f).load()

    # Inter-pass: cache/associate the objects (async)
    for n_cls, n_id in collected:
        await cache.obtain(n_cls, *n_id)

    # Pass 2: gather the objects we need to associate/cache (sync)
    class AssociatingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(
            pid: 'ACVDataclassAndID[_P, _T_co]',
        ) -> 'ACVDataclass[_P, _T_co]':
            cls, id_ = pid
            assert issubclass(cls, ACVDataclass)
            return cache._obtain_mapped(cls, *id_)  # noqa: SLF001 (sync)

    f.seek(0, os.SEEK_SET)
    return AssociatingUnpickler(f).load()


__all__ = [
    'pickle_and_reduce_to_identities',
    'unpickle_and_reconstruct_from_identities',
]
