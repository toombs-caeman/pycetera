import functools
import inspect
import unittest

import operator
import builtins

from decorators import singleton
from operator import *

ALLOWED_METHODS = dir(operator) + dir(builtins)


class L:
    """a lambda constructor interface"""
    def __init__(self):
        self.__stack__ = []
        self._f = None

    def __delay__(self, func, *args):
        requires = len(inspect.signature(func).parameters) - len(args)

        # can't use functools.partial because it gets the arguments backwards
        @functools.wraps(func)
        def newfunc(*fargs):
            return func(*fargs, *args)

        self.__stack__.append((
            requires,
            newfunc,
        ))

    def __getitem__(self, item):
        if self._f:
            self.__delay__(attrgetter, self._f.__name__)
            self._f = None
        self.__delay__(getitem, item)
        return self

    def __getattribute__(self, item):
        try:
            return object.__getattribute__(self, item)
        except:
            pass
        if self._f:
            self.__delay__(attrgetter, self._f.__name__)
            self._f = None

        # if item is in the local namespace, then use that as a function for _f
        if item in ALLOWED_METHODS:
            self._f = eval(item)
        else:
            self.__delay__(lambda x, y: getattr(x, y), item)
        return self

    def __call__(self, *args, **kwargs):
        if self._f:
            self.__delay__(self._f, *args, **kwargs)
            self._f = None
            return self
        # given a list of callables return a function which calls them in order
        # and tries to insert arguments where they go
        args = list(args)
        if sum(map(lambda x: x[0], self.__stack__)) + 1 != len(args) + len(self.__stack__):
            raise ValueError("number of args doesn't match number of slots", args, self.__stack__)
        for p, f in self.__stack__:
            v = f(*args[:p])
            args = [v] + args[p:]
        else:
            return args[0]
        return v


@singleton()
class X:
    def __getattribute__(self, item):
        return getattr(L(), item)

    def __getitem__(self, item):
        return L()[item]

    def __call__(self, *args, **kwargs):
        return L()(*args, **kwargs)


class TestLambda(unittest.TestCase):

    def test_lambda_map(self):
        g = list(range(10))
        self.assertEqual(list(map(X.gt(3), g)), [i > 3 for i in g])
        self.assertEqual(list(map(X.mul(3), g)), [i * 3 for i in g])
        self.assertEqual(list(map(X.pow(2), g)), [i * i for i in g])

    def test_lambda_filter(self):
        g = list(range(10))
        self.assertEqual(list(filter(X.gt(3), g)), [i for i in g if i > 3])
        self.assertEqual(list(filter(X.mod(2), g)), [i for i in g if i % 2])

    def test_lambda_reduce(self):
        self.assertEqual(functools.reduce(X.add(), range(10)), 45)
        self.assertEqual(functools.reduce(X.mul(), range(10)), 0)
        self.assertEqual(functools.reduce(X.add(), [1, 2, 3]), 6)

    def test_lambda_getattr(self):
        o = [type('', (), {"v": i})() for i in range(10)]
        self.assertEqual(list(map(X.v, o)), [i.v for i in o])
        pass

    def test_lambda_getitem(self):
        s = ('e{}', 'ump', 'hello {}!', 'wazzup home {}')
        self.assertEqual(list(map(X[1:], s)), [i[1:] for i in s])

    def test_lambda_combobreaker(self):
        """check long lambda constructions"""
        s = ('{}', 'ump', 'hello {}!', 'wazzup home {}')
        g = list(range(10))
        self.assertEqual(list(filter(X.contains('h'), s)), [i for i in s if 'h' in i])
        # special case: check for reversed math functions
        self.assertEqual(list(map(X.mul(2.), g)), [i * 2. for i in g])

    def test_emulations(self):
        # TODO write a few more
        _types = [1, 'a', 4.7]
        # g=list(range(7,10))
        s = ('{}', 'ump', 'hello {}!', 'wazzup home {}')
        self.assertEqual(list(map(X.isinstance(int), _types)), [isinstance(x, int) for x in _types])
        self.assertEqual(list(map(X.len(), s)), [len(i) for i in s])


if __name__ == '__main__':
    unittest.main()
