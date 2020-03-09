import functools
import inspect
import unittest

from decorators import singleton
from operator import *

attr = attrgetter
call = methodcaller

class rpartial(functools.partial):
    """exactly like functools.partial, but it reverses the order of supplied and enclosed positional arguments"""
    def __call__(*args, **keywords):
        if not args:
            raise TypeError("descriptor '__call__' of partial needs an argument")
        self, *args = args
        newkeywords = self.keywords.copy()
        newkeywords.update(keywords)
        return self.func(*args, *self.args, **newkeywords)

@singleton()
class X:
    """a lambda constructor interface"""
    def __init__(self, *, stack=(), flag=None):
        self.__stack = stack
        self.__flag = flag

    def __delay__(self, func, *args, **kwargs):
        if func in (methodcaller, itemgetter, attrgetter):
            f = func(*args, **kwargs)
            req = 1
        else:
            f = rpartial(func, *args, **kwargs)
            req = len(inspect.signature(f).parameters)
        return type(self)(stack=(*self.__stack,(req, f)))

    def __getitem__(self, item):
        if self.__flag:
            raise AttributeError()
        return self.__delay__(itemgetter, item)

    def __getattr__(self, item):
        if self.__flag:
            raise AttributeError()
        return type(self)(stack=self.__stack, flag=eval(item))

    def __call__(self, *args, **kwargs):
        if self.__flag:
            return self.__delay__(self.__flag, *args, **kwargs)
        # given a list of callables return a function which calls them in order
        # and tries to insert arguments where they go
        args = list(args)
        # compare the number of arguments needed to the number of arguments given + produced
        if sum(map(itemgetter(0), self.__stack)) + 1 != len(args) + len(self.__stack):
            # pass
            raise ValueError("number of args doesn't match number of slots", args, self.__stack)
        for p, f in self.__stack:
            v = f(*args[:p])
            args = [v] + args[p:]
        else:
            return args[0]
        return v



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
        self.assertEqual(list(map(X.attr('v'), o)), [i.v for i in o])
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
