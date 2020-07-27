import functools
import unittest
from inspect import signature


def decorator(wrapper):
    """
    Wrap function as a simple decorator.

    Does not handle decorators that accept extra arguments
    """
    @functools.wraps(wrapper)
    def dec(wrapped):

        sig = signature(wrapped)

        @functools.wraps(wrapped)
        def bind_args(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            return wrapper(wrapped, *bound.args, **bound.kwargs)

        return bind_args

    return dec


class boundmethod:
    """Method is bound to its class when not bound to an instance."""

    def __init__(self, f):
        self.__func__ = f

    def __get__(self, obj, cls):
        return functools.partial(self.__func__, cls if obj is None else obj)



@decorator
def trace(f, *args, **kwargs):
    print("calling %s with args %s, %s" % (f.__name__, args, kwargs))
    return f(*args, **kwargs)


def static_vars(**kw):
    def wrapper(f):
        for k, v in kw.items():
            setattr(f, k, v)
        return f

    return wrapper


class Doxception(Exception):
    """
    Doxception prepends its docstring to its output.
    """

    def __init__(self, *args):
        super().__init__(" ".join((self.__doc__, *args)))


class ExampleException(Doxception):
    """It let's you write things like this."""


class TestDecorators(unittest.TestCase):
    def test_static_vars(self):
        @static_vars(count=0)
        def counter():
            counter.count += 1
            return counter.count

        self.assertEqual(counter(), 1)
        self.assertEqual(counter(), 2)
        self.assertEqual(counter(), 3)


if __name__ == '__main__':
    unittest.main()

