# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

"""asynccachedview core.

Helpers to restrict return values of awaitable properties.
"""

import typing


def inspect_return_type(coroutine):
    th = typing.get_type_hints(coroutine)
    assert 'return' in th, f'{coroutine} lacks a return type annotation'
    ra = th['return']
    if typing.get_origin(ra) is tuple:
        tgt_cls, *el = typing.get_args(ra)
        if len(el) != 1 or el[0] is not ...:
            msg = f'{coroutine} returns a fixed-size tuple'
            raise TypeError(msg)
        return True, tgt_cls
    return False, ra
