import collections
import unittest
from abc import abstractmethod, ABC
from operator import getitem, setitem, delitem

# TODO make use of composable
# TODO make use of ReversableFunc
# TODO write docs
"""
see also
* https://python-lenses.readthedocs.io/en/latest/tutorial/optics.html
"""

# sentinels
_none = object()
_delete = object()

_get_op = (getattr, getitem, setattr, setitem, delattr, delitem)


class Optic(tuple, ABC):
    def __new__(cls, *args):
        return tuple.__new__(cls, args)

    @abstractmethod
    def __call__(self, obj, value=_none):
        pass

    def __append(self, other, T):
        """Append operation."""
        # wrap other when targeting MultiOptics
        if issubclass(T, MultiOptic) and not isinstance(other, Optic):
            other = constant(other)
        # reduce nesting if self is already the right type
        if isinstance(self, T):
            return T(*self, other)
        # map scalar op over items if self is a MultiOptic and target is not
        if T == getter and isinstance(self, MultiOptic):
            is_item, item = other
            return T(*(_get_op[is_item](x, item) for x in self))
        # nest
        return T(self, other)

    def __getattr__(self, item):
        return self.__append((False, item), getter)

    def __getitem__(self, item):
        return self.__append((True, item), getter)

    def __add__(self, other):
        return self.__append(other, opt)

    def __radd__(self, other):
        return constant(other) + self

    def __mul__(self, other):
        return self.__append(other, vec)

    def __rmul__(self, other):
        return constant(other) * self

    def __rshift__(self, other):
        return self.__append(other, composition)

    def __rrshift__(self, other):
        return constant(other) >> self

    def __invert__(self):
        return map_optic(self)

    # descriptor methods
    def __get__(self, instance, owner):
        return self(instance)

    def __set__(self, instance, value):
        return self(instance, value)

    def __delete__(self, instance):
        return self(instance, _delete)


class MultiOptic(Optic, ABC):
    """Flag Optics as containing other optics."""


class constant(Optic):
    def __repr__(self):
        return repr(*self)

    def __call__(self, obj=_none, value=_none):
        """Const: return a constant value."""
        val, *_ = self
        return val


class getter(Optic):

    def __repr__(self):
        tail = "".join(
            f"[{repr(item)}]" if is_item else f".{item}"
            for is_item, item in self
        )
        return f'{type(self).__name__}(){tail}'

    def __call__(self, obj, value=_none):
        """Scalar: return a single value."""
        if not self:
            return obj

        *t, (f, *i) = self
        for f, i in t:
            print(f, _get_op[f], obj, i)
            obj = _get_op[f](obj, i)

        if value is _delete:
            f += 4
        elif value is not _none:
            f += 2
            i += (value,)
        return _get_op[f](obj, *i)


class opt(MultiOptic):
    def __repr__(self):
        return f'({"+".join(repr(x) for x in self)})'

    def __call__(self, obj, value=_none):
        """Sum: return the first item to successfully evaluate."""
        for optic in self:
            try:
                v = optic(obj)
                if value is _none:
                    return v
                return optic(obj, value)
            except:
                continue
        raise TypeError


class vec(MultiOptic):
    def __repr__(self):
        return "*".join(repr(x) for x in self)

    def __call__(self, obj, value=_none):
        """Product: return a tuple of values."""
        return tuple(optic(obj, value) for optic in self)


class map_optic(MultiOptic):
    def __repr__(self):
        return f'~({repr(*self)})'

    def __call__(self, obj, value=_none):
        """Map: return a value for each object passed in."""
        optic, *_ = self
        return tuple(optic(x, value) for x in obj)


class composition(MultiOptic):
    def __repr__(self):
        return ">>".join(repr(x) for x in self)

    def __call__(self, obj, value=_none):
        """Compose: chain items together."""
        *optics, last = self
        for optic in optics:
            obj = optic(obj)
        return last(obj, value)


def view(**kwargs):
    """
    Access a set of optics as members of an object.
    """
    T = collections.namedtuple('view', kwargs.keys())
    # allow binding
    T.__rrshift__ = lambda s, o: type(s)(*(o >> x for x in s))
    return T(*kwargs.values())


# an empty getter is equivalent to the identity function
X = getter()


class TestOptic(unittest.TestCase):
    def setUp(self):
        self.nonce_type = type('nonce', (list,), {
            'foo': 'bar'
        })
        self.nonce = self.nonce_type((5, 4, 3))
        self.json = [
            {"color": "red", "value": "#f00"},
            {"color": "green"},
            {"color": "blue", "value": "#00f"},
            {"color": "cyan", "value": "#0ff"},
            {"color": "magenta", "value": "#f0f"},
            {"color": "yellow", "value": "#ff0"},
            {"color": "black", "value": "#000"}
        ]

    def test_getter(self):
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
        X.foo(self.nonce, s)
        self.assertEqual(s, self.nonce.foo)

        # setitem
        X[0](self.nonce, 1)
        self.assertEqual(
            1,
            self.nonce[0],
        )

    def test_vec(self):
        x = X[1] * X * X[0]
        l = [5, 4, 3]
        self.assertEqual((l[1], l, l[0]), x(l))

    def test_opt(self):
        o = X[0] + None
        self.assertEqual(o([]), None)
        self.assertEqual(o([1]), 1)

    def test_map(self):
        self.assertEqual(
            list((~X["color"])(self.json)),
            list(map(X["color"], self.json)),
        )

    def test_descriptor(self):
        t = [5, 4, 3]

        class List(list):
            first = X[0]
            second = X[1]
            third = X[2]
            stale = t >> X[0]

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

    def test_view(self):
        d = {'a': 1}
        v = view(b=X['a'])
        self.assertEqual(1, v.b(d))
        v = d >> v  # bind v to d
        # TODO this fails, descriptor not set up correctly?
        self.assertEqual(1, v.b)
        v.b = 3
        self.assertEqual(d, {'a':3})
        print(d)  # {'a':3}


if __name__ == '__main__':
    unittest.main()
