import collections
import unittest
from abc import ABC, abstractmethod
from operator import getitem, setitem, delitem
from types import FunctionType
from typing import Callable

"""
# TODO
* docs
* tests

# see also
* https://python-lenses.readthedocs.io/en/latest/tutorial/optics.html
"""

__all__ = ['inspect', 'Optic', 'X', 'view']

# sentinels
none = object()
delete = object()

# 'types'
const = 0
scalar = 1
add = 2
mul = 3
invert = 4
compose = 5


def inspect(optic):
    T, *i = optic
    return tuple((T, *(inspect(x) if isinstance(x, Optic) else x for x in i)))


class Optic(tuple):
    """
    Generate Lenses, Prisms, and Traversals.

    ## Examples

    X.attr      # lambda x:x.attr               # get attributes
    X[3]        # lambda x:x[3]                 # get items

    """

    def __new__(cls, sequence=None):
        # Internally, the morphism represents (T, *items)
        #   where T is an integer representing the morphism 'type'
        # The constant morphism contains a single value which it always returns
        # The scalar morphism contains a sequence representing attribute and item operations
        # All other morphisms contain a sequence of other morphisms.
        # Hence why default is (scalar,) and not (). It represents the identity function.

        return tuple.__new__(cls, sequence or (scalar,))

    # The following __functions capture the core functionality
    # they are dispatched by __call__

    # CONST
    def __const(self, obj=none, value=none):
        """Const: return a constant value."""
        _, val = self
        return val

    __get_op = (getattr, getitem, setattr, setitem, delattr, delitem)

    def __get(self, obj, value=none):
        """Scalar: return a single value."""
        if len(self) == 1:
            return obj

        _, *t, (f, *i) = self
        for f, i in t:
            obj = self.__get_op[f](obj, i)

        if value is delete:
            f += 4
        elif value is not none:
            f += 2
            i += (value,)
        return self.__get_op[f](obj, *i)

    def __add(self, obj, value=none):
        """Sum: return the first item to successfully evaluate."""
        for optic in self:
            try:
                v = optic(obj)
                if value is none:
                    return v
                return optic(obj, value)
            except:
                continue
        raise TypeError

    def __mul(self, obj, value=none):
        """Product: return a tuple of values."""
        _, *items = self
        return tuple(optic(obj, value) for optic in items)

    def __invert(self, obj, value=none):
        """Map: return a value for each object passed in."""
        _, optic = self
        return tuple(optic(x, value) for x in obj)

    def __rshift(self, obj, value=none):
        """Compose: chain items together."""
        _, *optics, last = self
        for optic in optics:
            obj = optic(obj)
        return last(obj, value)

    # dunder methods

    __repr = (
        lambda a: repr(*a),
        lambda a: f'X{"".join((f"[{repr(item)}]" if is_item else f".{item}") for is_item, item in a)}',
        lambda a: f'({"+".join(repr(x) for x in a)})',
        lambda a: "*".join(repr(x) for x in a),
        lambda a: f'~({repr(*a)})',
        lambda a: ">>".join(repr(x) for x in a),
    )

    def __repr__(self):
        T, *a = self
        return self.__repr[T](a)

    __handlers = (__const, __get, __add, __mul, __invert, __rshift)

    def __call__(self, obj=none, value=none):
        return self.__handlers[super().__getitem__(0)](self, obj, value)

    def __append(self, other, T):
        """Append operation."""
        s_T, *i = self
        # wrap other when targeting vector types
        if T > scalar and not isinstance(other, type(self)):
            other = type(self)((const, other))
        # map scalar op over items if self is a vector type and target is not
        if s_T > scalar and T == scalar:
            is_item, item = other
            return type(self)((T, *(self.__get_op[is_item](x, item) for x in i)))
        # reduce nesting if self is already the right type
        if s_T == T:
            return type(self)(tuple(self) + (other,))
        # nest
        return type(self)((T, self, other))

    def __getattr__(self, item):
        return self.__append((False, item), scalar)

    def __getitem__(self, item):
        return self.__append((True, item), scalar)

    def __add__(self, other):
        return self.__append(other, add)

    def __radd__(self, other):
        return type(self)((const, other)) + self

    def __mul__(self, other):
        return self.__append(other, mul)

    def __rmul__(self, other):
        return type(self)((const, other)) * self

    def __rshift__(self, other):
        return self.__append(other, compose)

    def __rrshift__(self, other):
        return type(self)((const, other)) >> self

    def __invert__(self):
        return type(self)((invert, self))

    # descriptor methods
    def __get__(self, instance, owner):
        return self(instance)

    def __set__(self, instance, value):
        return self(instance, value)

    def __delete__(self, instance):
        return self(instance, delete)


def view(**kwargs):
    """
    Access a set of optics as members of an object.

    example:
    d = {'a':1}
    v = view(d, b=X['a'])
    print(v.b) # 1
    v.b = 3
    print(d) # {'a':3}
    """
    T = collections.namedtuple('view', kwargs.keys())
    # allow binding
    T.__rrshift__ = lambda s, o: type(s)(*(o >> x for x in s))
    return T(*kwargs.values())


X = Optic()


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

    def test_scalar(self):
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

    def test_exponential(self):
        self.assertEqual(
            list((~X["color"])(self.json)),
            list(map(X["color"], self.json)),
        )


if __name__ == '__main__':
    unittest.main()
