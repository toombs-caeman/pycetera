import unittest
from taxonomy import *


def handler(function, name='', bases=(), coerce=False):
    """
    Returns a type that handles all non-coerced magic methods with the given function.
    """
    def decorate(m):
        def method_wrapper(self, *args, **kwargs):
            return function(self, m, *args, **kwargs)
        return method_wrapper

    return type(name, bases, {
        f'__{m.__name__.strip("_")}__': decorate(m)
        for m in
        (operators if coerce else non_coercing_operators)
    })


_Passthrough = handler(lambda s, m, *a, **k: getattr(s._, m)(*a, **k), coerce=True)

class Passthrough(_Passthrough):
    """Object behaves like passed argument (even with magic methods), but can contain extra attributes"""
    def __init__(self, obj):
        self._ = obj

    def __getattr__(self, item):
        return getattr(self._, item)


_Recorder = handler(lambda s, *a, **k: type(s)(tuple(s) + ((*a, k),)))
class Recorder(_Recorder, tuple):
    """alternative methodcaller/attrgetter/itemgetter"""
    __set = {getattr: setattr, getitem: setitem}
    __iter__ = tuple.__iter__
    _ = _Recorder.__call__

    def __call__(self, obj, *value):
        if not self:
            return obj
        *t, (m, *a, k) = self
        if value:
            m = self.__set[m]
        for method, *args, kwargs in t:
            obj = method(obj, *args, **kwargs)
        return m(obj, *a, *value, **k)

    def _bind(self, obj):
        self.__obj = obj

    def __get__(self, instance, owner):
        return self(self.__obj if hasattr(self, '__obj') else instance)

    def __set__(self, instance, value):
        return self(self.__obj if hasattr(self, '__obj') else instance, value)


class TestLens(unittest.TestCase):
    def setUp(self):
        class nonce(list):
            foo = 'bar'

            def n(self, n):
                return n

            def __repr__(self):
                return f'nonce({super().__repr__()})'

        self.nonce = nonce((5, 4, 3))
        self.json = [
            {"color": "red", "value": "#f00"},
            {"color": "green"},
            {"color": "blue", "value": "#00f"},
            {"color": "cyan", "value": "#0ff"},
            {"color": "magenta", "value": "#f0f"},
            {"color": "yellow", "value": "#ff0"},
            {"color": "black", "value": "#000"}
        ]
        self.X = Recorder()

    def test_lens(self):
        self.assertEqual(
            self.X(self.nonce),
            self.nonce,
        )
        # getattr
        self.assertEqual(
            self.X.foo(self.nonce),
            self.nonce.foo,
        )
        # getitem
        self.assertEqual(
            self.X[1](self.nonce),
            self.nonce[1],
        )
        # call
        self.assertEqual(
            self.X.n._(3)(self.nonce),
            self.nonce.n(3),
        )
        # slice
        self.assertEqual(
            self.X[:1](self.nonce),
            self.nonce[:1],
        )

        # math
        self.assertEqual(
            (1 + self.X[0] + 1)(self.nonce),
            7,
        )

    def test_descriptor(self):
        t = [5, 4, 3]

        class List(list):
            first = self.X[0]
            second = self.X[1]
            third = self.X[2]
            stale = self.X[0]._bind(t)

        # get
        c = List(t)
        self.assertEqual(tuple(t), (c.first, c.second, c.third))

        # set
        c.first = 9
        self.assertEqual((9, *t[1:]), (c.first, c.second, c.third))

        self.assertEqual(t[0], c.stale)
        c.stale = 3
        self.assertEqual(t[0], 3)


if __name__ == '__main__':
    unittest.main()
