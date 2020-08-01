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
    if fillvalue is no_fill:
        return map(f, *i)
    return map(lambda args: f(*args), zip_longest(*i, fillvalue=fillvalue))


class Doxception(Exception):
    """
    Doxception prepends its docstring to its output.
    """

    def __init__(self, *args):
        super().__init__(" ".join((self.__doc__, *args)))


class ExampleException(Doxception):
    """It let's you write things like this."""
