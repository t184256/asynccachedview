# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module for defining cached dataclasses and operating on them."""

from asynccachedview.dataclasses._core import (
    ACVDataclass,
    awaitable_property,
    primary_key,
)

__all__ = [
    'ACVDataclass',
    'awaitable_property',
    'primary_key',
]
