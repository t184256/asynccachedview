# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import pytest

import asynccachedview


def test_bad_dataclass_identity():
    """Test dataclass specifying non-existing fields for identity."""
    with pytest.raises(AssertionError):
        @asynccachedview.dataclass(identity=('id', 'nonex'))
        class _:
            """Example dataclass."""

            id: int

            @classmethod
            async def __obtain__(cls, id_):
                return cls(id=id_)
