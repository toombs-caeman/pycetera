import builtins
from functools import *
from itertools import *

no_fill = object()


@wraps(builtins.zip)
def zip(*iterables, fillvalue=no_fill):
    if fillvalue is no_fill:
        return builtins.zip(*iterables)
    return zip_longest(*iterables, fillvalue=fillvalue)


@wraps(map)
def map(f, *i, fillvalue=no_fill):
    if not i:
        return partial(map, f, fillvalue=fillvalue)
    if fillvalue is no_fill:
        return builtins.map(f, *i)
    return builtins.map(lambda args: f(*args), zip_longest(*i, fillvalue=fillvalue))


def compose(*functions):
    return lambda obj: reduce(lambda o, f: f(o), reversed(functions), obj)


def compose_with(*functions):
    return partial(compose, *functions)


class Doxception(Exception):
    """
    Doxception prepends its docstring to its output.
    """

    def __init__(self, *args):
        super().__init__(" ".join((self.__doc__, *args)))


class ExampleException(Doxception):
    """It let's you write things like this."""
