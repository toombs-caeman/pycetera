import functools
import itertools
import unittest
from inspect import signature, Parameter

import cast

# re-export common types
from numbers import Number
from types import *
from collections.abc import *
from collections import namedtuple

# extended functions
# see https://funcy.readthedocs.io/en/latest/extended_fns.html#extended-fns
AnoCast = cast.cast()
AnoCast.register(lambda y: lambda x: x, type(None), Callable)
AnoCast.register(lambda y: lambda x: y[x], Mapping, Callable)
AnoCast.register(lambda y: lambda x: x in y, set, Callable)


def anodize(f):
    """
    Make use of function annotations to implement 'semi-static' typing.

    * cast arguments to the expected type.
    * cast return values to the expected type.
    * lift functions.

    """
    sig = signature(f)

    @functools.wraps(f)
    def inner(*args, **kwargs):
        # print("raw args", args, kwargs)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        # print("bound args", bound.arguments)

        try_map = False

        # cast arguments if they need it
        for param in sig.parameters.values():
            arg = bound.arguments[param.name]
            if param.annotation and not isinstance(arg, param.annotation):
                try:
                    bound.arguments[param.name] = AnoCast.cast(arg, param.annotation)
                except:
                    # casting failed
                    if isinstance(arg, Iterable):
                        try_map = True

        # print("cleaned args", bound.arguments)
        # lift
        if try_map:
            for param in sig.parameters.values():
                arg = bound.arguments[param.name]
                # everything gets repeated unless it is an iterable that couldn't be cast
                if not param.annotation or \
                        isinstance(arg, param.annotation) or \
                        not isinstance(arg, Iterable):
                    bound.arguments[param.name] = itertools.repeat(arg)
                else:
                    bound.arguments[param.name] = iter(arg)

            # define function because map doesn't allow keywords
            # and simply yielding turns inner() into a generator always
            def _map():
                try:
                    while True:
                        # Don't use generator expressions here on account of PEP 479
                        a = []
                        for arg in bound.args:
                            a.append(next(arg))
                        kw = {}
                        for k, v in bound.kwargs.items():
                            kw[k] = v
                        yield inner(*a, **kw)
                except StopIteration:
                    return

            return _map()

        # cast the returned type
        return AnoCast.cast(
            f(*bound.args, **bound.kwargs),
            object if sig.return_annotation is Parameter.empty else sig.return_annotation,
        )

    return inner


class TestAnodize(unittest.TestCase):
    def test_lift(self):
        @anodize
        def add(a: Number, b: Number) -> Number:
            return a + b

        self.assertEqual(add(3, 4), 3 + 4)
        self.assertEqual(
            list(add([3, 4], 5)),
            [x + 5 for x in [3, 4]],
        )

        self.assertEqual(
            list(add([3, 4], [5, 6, 7])),
            [x + y for x, y in zip([3, 4], [5, 6, 7])],
        )

    def test_extended_functions(self):
        @anodize
        def call(a: int, f: Callable = None):
            return f(a)

        # identity (plus an arg cast)
        self.assertEqual(
            call(3.5),
            int(3.5),
        )
        # Mapping
        self.assertEqual(
            call(3.5, {3:'a'}),
            'a',
        )
        # set
        self.assertEqual(
            call(3.5, {3}),
            True,
        )


if __name__ == '__main__':
    unittest.main()
