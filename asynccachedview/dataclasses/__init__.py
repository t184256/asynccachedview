# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module for defining cached dataclasses and operating on them."""

from asynccachedview.dataclasses._core import (
    dataclass, awaitable_property, obtain_related, associate_related
)

__all__ = ['dataclass', 'awaitable_property',
           'obtain_related', 'associate_related']
