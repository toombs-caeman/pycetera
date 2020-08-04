import unittest
from operator import getitem, setitem, delitem


class Lens(tuple):
    """Combine the functionality of itemgetter, attrgetter, and methodcaller."""
    __none = object()
    __delete = object()
    __op = (
        lambda _, o: o, lambda f, a, k: f(*a, **k),
        getattr, getitem,
        setattr, setitem,
        delattr, delitem,
    )
    __fmt = (
        repr,
        lambda a, kw: f'._({", ".join((*map(repr, a), *(f"{k}={repr(v)}" for k, v in kw.items())))})',
        ".{}".format,
        lambda x: f'[{repr(x)}]',
    )

    def __bound(self):
        return self and tuple.__getitem__(self, 0)[0] == 0

    def __call__(self, obj=__none, value=__none):
        if self.__bound():
            value = obj
        elif obj is self.__none:
            raise ValueError('unbound lens requires argument')
        elif not self:
            return obj

        *t, (f, *i) = self

        if value is self.__delete:
            if f < 2:
                raise (
                    ValueError("can't delete lens const"),
                    SyntaxError("can't delete function call"),
                )[f]
            f += 4
        elif value is not self.__none:
            if f < 2:
                raise (
                    ValueError("can't assign to lens const"),
                    SyntaxError("can't assign to function call"),
                )[f]
            f += 2
            i += (value,)

        for f_, *i_ in t:
            obj = self.__op[f_](obj, *i_)
        return self.__op[f](obj, *i)

    def __repr__(self):
        t = "".join(self.__fmt[f](*i) for f, *i in self)
        return f'lambda:{t}' if self.__bound() else f'{type(self).__name__}(){t}'

    # appending operators
    def __add__(self, other):
        return type(self)((*self, *other)) if isinstance(other, type(self)) else NotImplemented

    def __radd__(self, other):
        return type(self)(((0, other), *self))

    def _(self, *args, **kwargs):
        return type(self)((*self, (1, args, kwargs)))

    def __getattr__(self, item):
        return type(self)((*self, (2, item)))

    def __getitem__(self, item):
        return type(self)((*self, (3, item)))

    # descriptor methods
    def __get__(self, instance, owner):
        return self() if self.__bound() else self(instance)

    def __set__(self, instance, value):
        return self(value) if self.__bound() else self(instance, value)

    def __delete__(self, instance=__none):
        return self(self.__delete) if self.__bound() else self(instance, self.__delete)


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
        self.X = Lens()

    def test_lens(self):
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
        # setattr
        s = 'monty'
        self.X.foo(self.nonce, s)
        self.assertEqual(s, self.nonce.foo)

        # setitem
        self.X[0](self.nonce, 1)
        self.assertEqual(
            1,
            self.nonce[0],
        )

    def test_descriptor(self):
        t = [5, 4, 3]

        class List(list):
            first = self.X[0]
            second = self.X[1]
            third = self.X[2]
            stale = t + self.X[0]

        # get
        c = List(t)
        self.assertEqual(tuple(t), (c.first, c.second, c.third))

        # set
        c.first = 9
        self.assertEqual((9, *t[1:]), (c.first, c.second, c.third))

        self.assertEqual(t[0], c.stale)
        c.stale = 3
        self.assertEqual(t[0], 3)

        # del
        del c.stale
        self.assertEqual(t, [4, 3])


if __name__ == '__main__':
    unittest.main()
