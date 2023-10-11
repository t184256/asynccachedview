# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module for defining cached dataclasses and operating on them."""

from asynccachedview.cache._cache import Cache, get_cache

__all__ = ['Cache', 'NoCache', 'get_cache']
