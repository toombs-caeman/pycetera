import unittest
from operator import getitem, setitem, delitem


class Lens(tuple):
    """
    Combine the functionality of map, itemgetter, attrgetter, and methodcaller.

    X.bar(foo) # return foo.bar
    X['bar'](foo) # return foo['bar']
    X._('bar')(foo) # return foo('bar')
    X[:].bar[3](foo) # return [i.bar[3] for i in foo]

    """
    __delete = object()
    __op = (
        lambda f, a, k: f(*a, **k),
        getattr, getitem,
        setattr, setitem,
        delattr, delitem,
    )
    __fmt = (
        lambda a, kw: f'._({", ".join((*map(repr, a), *(f"{k}={v!r}" for k, v in kw.items())))})',
        ".{}".format,
        lambda x: f'[{x!r}]',
    )

    def __call__(self, obj, *value):
        if not self:
            return obj

        # the last action requires some pre-processing, so split that off
        *t, (f, *i) = self

        # drop trailing hammers
        while f < 0 and t:
            *t, (f, *i) = t

        # if we still don't have a valid end function, then it was hammers all the way through
        if f < 0:
            return obj

        # if we're setting or deleting, adjust f
        if value:
            if value[0] is self.__delete:
                if not f:
                    raise SyntaxError("can't delete function call")
                f += 4
            else:
                if not f:
                    raise SyntaxError("can't assign to function call")
                f += 2
                i += value

        # apply the operation to obj in succession.
        for p, (f_, *i_) in enumerate(t):
            if f_ < 0:
                # a hammer
                tail_call = type(self)(tuple(self)[p + 1:])
                return [tail_call(o, *value) for o in obj]
            obj = self.__op[f_](obj, *i_)
        return self.__op[f](obj, *i)

    def __repr__(self):
        return f'{type(self).__name__}{"".join(self.__fmt[f](*i) for f, *i in self)}'

    # appending operators
    def _(self, *args, **kwargs):
        return type(self)((*self, (0, args, kwargs)))

    def __getattr__(self, item):
        return type(self)((*self, (1, item)))

    def __getitem__(self, item):
        if item == slice(None):
            # this is the map "hammer operator"
            return type(self)((*self, (-1,)))

        return type(self)((*self, (2, item)))

    # descriptor methods
    def __get__(self, instance, owner):
        return self(instance)

    def __set__(self, instance, value):
        return self(instance, value)

    def __delete__(self, instance):
        return self(instance, self.__delete)

X = Lens()

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
