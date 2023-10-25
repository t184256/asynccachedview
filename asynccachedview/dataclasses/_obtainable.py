# SPDX-FileCopyrightText: 2023 Alexander Sosedkin <monk@unboiled.info>
# SPDX-License-Identifier: GPL-3.0

import typing

_T_co = typing.TypeVar('_T_co', covariant=True)
_P = typing.ParamSpec('_P')


@typing.runtime_checkable
class Obtainable(typing.Protocol[_P, _T_co]):
    # Because of https://github.com/python/typing/issues/548,
    # (I can express either "returns same type" or "returns an obtainable",
    #  but not both)
    # so I'm weazeling out of it with a recursive type, _T_co must be a forward
    # reference to the very Obtainable being defined.
    # Maybe intersections would've helped.
    @classmethod
    async def __obtain__(  # noqa: PLW3201
        cls: type[_T_co],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> 'Obtainable[_P, _T_co]': ...  # protocol
