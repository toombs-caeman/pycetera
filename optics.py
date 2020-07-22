import unittest
from operator import getitem, setitem


class Optic(tuple):
    """
    Abstract Base Class

    Generate getter/setter functions.
    Does not appreciate method calls.

    Lens.attr <=> lambda x:x.attr
    Lens[3] <=> lambda x:x[3]
    Lens.attr[3].f[2:4] <=> lambda x:x.attr[3].f[2:4]
    (Lens.foo << 3) <=> lambda x:setattr(x,'foo',3)
    """

    def __call__(self, obj):
        """Getter. Apply the Optic to an object."""
        raise NotImplementedError()

    def __lshift__(self, other):
        """
        Setter.

        This is a terminal symbol for the lens since setters do not return anything, and so cannot chain.
        """
        raise NotImplementedError()

    def __invert__(self):
        """Return a (safe) copy of self with no setters."""
        return type(self)(~x for x in self)

    def __combine(self, other, T):
        if not isinstance(other, Optic):
            raise TypeError('Cannot combine Optic with type %s', type(other))
        if isinstance(self, T):
            if isinstance(other, T):
                return T(tuple(self) + tuple(other))
            return T(tuple(self) + (other,))
        if isinstance(other, T):
            return T((self,) + tuple(other))
        return T((self, other))

    def __mul__(self, other):
        return self.__combine(other, Spectra)

    def __add__(self, other):
        return self.__combine(other, Prism)

    def __getitem__(self, item):
        return Lens(_pre=self)[item]

    def __getattr__(self, item):
        return getattr(Lens(_pre=self), item)


class Lens(Optic):
    __ops = (getitem, getattr, setitem, setattr)
    __fmt = ("[{}]", ".{}", "[{}] << {}", ".{} << {}")

    def __init__(self, _tuple=(), *, _pre=None):
        super().__init__()
        self.__pre = _pre

    def __getitem__(self, item):
        return type(self)(tuple(self) + ((0, item),), _pre=self.__pre)

    def __getattr__(self, item):
        return type(self)(tuple(self) + ((1, item),), _pre=self.__pre)

    def __call__(self, obj):
        if self.__pre:
            obj = self.__pre(obj)
        for f, *i in self:
            obj = self.__ops[f](obj, *i)
        return obj

    def __repr__(self):
        return "{}{}".format(
             "X" if self.__pre is None else "({})".format(repr(self.__pre)),
            "".join(self.__fmt[f].format(*map(repr,i)) for f, *i in self),
        )

    def __invert__(self):
        return type(self)(((f % 2, *i) for f, *i in self), _pre=self.__pre)

    def __lshift__(self, value):
        *t, (func, item) = self
        return type(self)(tuple(t) + ((func + 2, item, value),), _pre=self.__pre)


class Prism(Optic):
    def __call__(self, obj):
        for l in self:
            ilens = ~l
            try:
                v = ilens(obj)
                if ilens == l:
                    return v
                return l(obj)
            except:
                continue
        raise TypeError()

    def __lshift__(self, value):
        return type(self)(x << value for x in self)

    def __repr__(self):
        return " + ".join(repr(x) for x in self)


class Spectra(Optic):
    def __call__(self, obj):
        return tuple(x(obj) for x in self)

    def __lshift__(self, values):
        if len(values) != len(self):
            raise ValueError
        return type(self)(x << i for x, i in zip(self, values))

    def __repr__(self):
        return " * ".join(repr(x) for x in self)


X = Lens()
json = [
    {"color": "red", "value": "#f00"},
    {"color": "green", "value": "#0f0"},
    {"value": "#00f"},
    {"color": "cyan", "value": "#0ff"},
    {"color": "magenta", "value": "#f0f"},
    {"color": "yellow", "value": "#ff0"},
    {"color": "black", }
]


class TestOptic(unittest.TestCase):
    def setUp(self) -> None:
        self.nonce_type = type('nonce', (list,), {
            'foo': 'bar'
        })
        self.nonce = self.nonce_type((5, 4, 3))
        self.json = [
            {"color": "red", "value": "#f00"},
            {"color": "green", "value": "#0f0"},
            {"color": "blue", "value": "#00f"},
            {"color": "cyan", "value": "#0ff"},
            {"color": "magenta", "value": "#f0f"},
            {"color": "yellow", "value": "#ff0"},
            {"color": "black", "value": "#000"}
        ]

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
        # slice
        self.assertEqual(
            X[:1](self.nonce),
            self.nonce[:1],
        )
        # setattr
        s = 'monty'
        (X.foo << s)(self.nonce)
        self.assertEqual(s, self.nonce.foo)
        # TODO setitem

    def test_spectra(self):
        # TODO
        pass

    def test_prism(self):
        # TODO
        pass


if __name__ == '__main__':
    unittest.main()
