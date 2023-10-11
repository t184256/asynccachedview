# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module for defining cached dataclasses and operating on them."""

from asynccachedview.dataclasses._core import (
    awaitable_property,
    dataclass,
    primary_key,
)

__all__ = [
    'awaitable_property',
    'dataclass',
    'primary_key',
]
