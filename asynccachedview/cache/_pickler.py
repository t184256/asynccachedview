# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module that implements pickling ACVDataclasses to identities and back."""

import io
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


def unpickle_and_collect_required(b):
    required = []

    class AssociatingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(pid):
            cls, id_ = pid
            assert issubclass(cls, _ACVDataclass)
            required.append((cls, id_))

    f = io.BytesIO(b)
    AssociatingUnpickler(f).load()
    return required


def unpickle_and_reconstruct_from_identities(b, cache):
    class AssociatingUnpickler(pickle.Unpickler):
        @staticmethod
        def persistent_load(pid):
            cls, id_ = pid
            assert issubclass(cls, _ACVDataclass)
            return cache._obtain_mapped(cls, *id_)  # noqa: SLF001

    f = io.BytesIO(b)
    return AssociatingUnpickler(f).load()


__all__ = [
    'pickle_and_reduce_to_identities',
    'unpickle_and_collect_required',
    'unpickle_and_reconstruct_from_identities',
]
