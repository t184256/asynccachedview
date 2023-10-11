# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""Module for a NoCache stub for when caching is not used."""

from asynccachedview._nocache._nocache import NoCache

__all__ = ['NoCache']
