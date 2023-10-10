# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Test assorted corner-cases."""

import pytest

import asynccachedview.dataclasses


def test_bad_dataclass_identity():
    """Test dataclass specifying non-existing fields for identity."""
    with pytest.raises(AssertionError):

        @asynccachedview.dataclasses.dataclass(identity=('id', 'nonex'))
        class _:  # noqa: N801
            """Example dataclass."""

            id: int  # noqa: A003

            @classmethod
            async def __obtain__(cls, id_):  # noqa: PLW3201
                return cls(id=id_)
