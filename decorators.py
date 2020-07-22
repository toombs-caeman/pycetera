import collections
import functools
import unittest

from inspect import signature
from itertools import repeat


def anomap(f):
    """
    Decorated function will map itself over arguments when annotated types don't match.
    if all annotations match it returns as written.
    if one or more annotations don't match, it instead returns a map of results.
    """
    sig = signature(f)

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        b = sig.bind(*args, **kwargs)
        b.apply_defaults()
        b = b.arguments
        should_map = [type(b.get(k)) != v for k, v in f.__annotations__.items()]
        if any(should_map):
            return map(
                f,
                *map(
                    lambda x, a: iter(a) if x else repeat(a),
                    should_map,
                    b.values(),
                )
            )
        return f(*args, **kwargs)

    return wrapper


def singleton(*a, **kw):
    def inner(klass):
        return klass(*a, **kw)

    return inner


def return_namedtuple(typename, field_names, *, rename=False, defaults=None, module=None):
    """wrap the return value of a function with collection.namedtuple"""
    retType = collections.namedtuple(typename, field_names, rename=rename, defaults=defaults, module=module)

    def dec(func):
        @functools.wraps(func)
        def wrapper(*a, **kw):
            return retType(*func(*a, **kw))

        return wrapper

    return dec


def static_vars(**kw):
    def wrapper(f):
        for k, v in kw.items():
            setattr(f, k, v)
        return f

    return wrapper


class Doxception(Exception):
    """Doxception prepends its docstring to its output"""

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

    def test_anomap(self):
        @anomap
        def f(x: int, y: int):
            return x + y

        self.assertEqual(f(1, 3), 4)
        self.assertEqual(list(f([3, 4], 1)), [4, 5])

    def test_singleton(self):
        littleL = [3, 5, 3]

        @singleton(littleL)
        class BigL(list):
            pass

        self.assertTrue(isinstance(BigL, list))
        self.assertEqual(BigL, littleL)

        @singleton()
        def f():
            return 3

        self.assertEqual(f, 3)

    def test_return_namedtuple(self):
        @return_namedtuple("result", ("first", "second", "sum"))
        def add(a, b):
            return a, b, a + b

        r = add(1, 3)
        self.assertEqual(r.sum, 4)


if __name__ == '__main__':
    unittest.main()
