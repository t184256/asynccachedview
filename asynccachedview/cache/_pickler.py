# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements pickling ACVDataclasses to identities and back."""

import io
import os
import pickle

import aiosqlitemydataclass

import asynccachedview.dataclasses._core

_ACVDataclass = asynccachedview.dataclasses._core.ACVDataclass  # noqa: SLF001


class DissociatingPickler(pickle.Pickler):
    @staticmethod
    def persistent_id(obj):
        if isinstance(obj, _ACVDataclass):
            return obj.__class__, aiosqlitemydataclass.identity(obj)
        return None


def pickle_and_reduce_to_identities(obj):
    f = io.BytesIO()
    DissociatingPickler(f).dump(obj)
    return f.getvalue()


async def unpickle_and_reconstruct_from_identities(b, cache):
    f = io.BytesIO(b)

    # Pass 1: gather the objects we need to associate/cache (sync)
    collected = []

    class CollectingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(pid):
            cls, id_ = pid
            assert issubclass(cls, _ACVDataclass)
            collected.append((cls, id_))

    CollectingUnpickler(f).load()

    # Inter-pass: cache/associate the objects (async)
    for n_cls, n_id in collected:
        await cache.obtain(n_cls, *n_id)

    # Pass 2: gather the objects we need to associate/cache (sync)
    class AssociatingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(pid):
            cls, id_ = pid
            assert issubclass(cls, _ACVDataclass)
            return cache._obtain_mapped(cls, *id_)  # noqa: SLF001 (sync)

    f.seek(0, os.SEEK_SET)
    return AssociatingUnpickler(f).load()


__all__ = [
    'pickle_and_reduce_to_identities',
    'unpickle_and_reconstruct_from_identities',
]
