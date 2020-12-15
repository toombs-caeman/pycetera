import unittest
from operator import getitem, setitem, delitem


class Lens(tuple):
    __op = (lambda f, a, k: f(*a, **k), getattr, getitem, setattr, setitem, delattr, delitem)
    _, __getattr__ = lambda s, *args, **kwargs: type(s)((*s, (0, args, kwargs))), lambda s, i: type(s)((*s, (1, i)))
    __getitem__ = lambda s, i: type(s)((*s, (-1,))) if i == slice(None) else type(s)((*s, (2, i)))
    __get__, __set__, __delete__ = lambda s, i, _: s(i), lambda s, i, v: s(i, v), lambda s, i: s(i, Lens)

    def __call__(s, o, *v):
        if not s: return o
        *t, (f, *i) = s
        while f < 0 and t: *t, (f, *i) = t
        if f < 0: return o
        if v:
            if not f: raise SyntaxError("can't assign or delete function call")
            f, i = (f + 4, i) if v[0] is Lens else (f + 2, i + list(v))
        for p, (f_, *i_) in enumerate(t):
            if f_ < 0:
                c = type(s)((*s,)[p + 1:])
                return [c(x, *v) for x in o]
            o = s.__op[f_](o, *i_)
        return s.__op[f](o, *i)


X = Lens()


All[:].expire._(end_date, True)(CIDR.objects....)

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

    def test_hammer(self):
        self.assertEqual(
            X[:]['color'](self.json),
            [x['color'] for x in self.json],
        )
        self.assertEqual(
            X[:](self.json),
            self.json,
        )

    def test_lens(self):
        # getattr
        self.assertEqual(
            X.foo(self.nonce),
            self.nonce.foo,
        )
        # getitem
        self.assertEqual(
            X[1](self.nonce),
            self.nonce[1],
        )
        # call
        self.assertEqual(
            X.n._(3)(self.nonce),
            self.nonce.n(3),
        )
        # slice
        self.assertEqual(
            X[:1](self.nonce),
            self.nonce[:1],
        )
        # setattr
        s = 'monty'
        X.foo(self.nonce, s)
        self.assertEqual(s, self.nonce.foo)

        # setitem
        X[0](self.nonce, 1)
        self.assertEqual(
            1,
            self.nonce[0],
        )

    def test_descriptor(self):
        t = [5, 4, 3]

        class List(list):
            first = X[0]
            second = X[1]
            third = X[2]

        # get
        c = List(t)
        self.assertEqual(tuple(t), (c.first, c.second, c.third))

        # set
        c.first = 9
        self.assertEqual((9, *t[1:]), (c.first, c.second, c.third))



if __name__ == '__main__':
    unittest.main()
