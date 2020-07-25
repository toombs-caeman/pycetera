import unittest
from operator import getitem, setitem, delitem

# see also https://python-lenses.readthedocs.io/en/latest/tutorial/optics.html

# sentinels
none = object()
delete = object()


# TODO
"""
* __pow__(n) to repeat an optic n times
* what would __truediv__ mean? reducing the number of outputs
* docs
* tests
"""

__inspect = ("const", "scalar", "sum", "product", "map")
def inspect(optic):
    T, *i = optic
    return tuple((__inspect[T], *(inspect(x) if isinstance(x, Optic) else x for x in i)))


class Optic(tuple):
    """
    Generate Lenses, Prisms, and Traversals.

    ## Examples

    X.attr      # lambda x:x.attr               # get attributes
    X[3]        # lambda x:x[3]                 # get items


    ## Binding
    Optics are 'unbound' by default, but can be bound to an object with left shift `<<`
    A bound optic doesn't take an object in it's call signature.
    If a bound optic is composed it loses it's biding.

    example:
    y = X*X << 3    # y is X*X bound to 3
    y()             # (3, 3)

    """

    #   Data Model
    # The first value determines the execution type
    # 0: const        get a constant value
    # 1: scalar       get/set/del single value
    # 2: sum          get/set/del one of several values
    # 3: product      get/set/del a fixed number of values > 1
    # 4: exponential  get/set/del N values

    # subsequent items are treated differently in each type.
    # In const there is a single value.
    # In scalars they are tuples (T, value) where 0 indicates value is an attribute and 1 an item.
    # In sum, product, and exponential types they are optics.
    # Exponential types can contain only a single optic.

    def __init__(self, _tuple=(), *, obj=none):
        # must have at least one element (the type)
        assert len(self)
        self.__obj = obj

    # BIND
    def __lshift__(self, other):
        """Bind"""
        return type(self)(self, obj=other)

    # HELPERS
    @property
    def __T(self):
        """Get type indicator."""
        return super().__getitem__(0)

    @property
    def __items(self):
        """Get content."""
        return super().__getitem__(slice(1, None))

    __repr = (
        lambda a: repr(*a),
        lambda a: f'X{"".join((f"[{repr(item)}]" if is_item else f".{item}") for is_item, item in a)}',
        lambda a: f'({"+".join(repr(x) for x in a)})',
        lambda a: "*".join(repr(x) for x in a),
        lambda a: f'~({repr(*a)})'
    )
    def __repr__(self):
        T, *a = self
        return self.__repr[T](a)

    # CONST
    def __const(self, obj, value=none):
        if value is none:
            return obj

    # SCALAR
    __scalar_op = (getattr, getitem, setattr, setitem, delattr, delitem)

    def __scalar(self, obj, value=none):
        if not self.__items:
            return obj

        # reduce over self[:-1]
        *t, (f, i) = self.__items
        for f, i in t:
            obj = self.__scalar_op[f](obj, i)

        i = (i,)
        if value is delete:
            f += 4
        elif value is not none:
            f += 2
            i += (value,)
        return self.__scalar_op[f](obj, *i)

    def __append(self, *args):
        return type(self)(tuple(self) + args)

    def __get(self, item, is_item):
        T, *i = self
        if T > 1:
            return type(self)((T, *(self.__scalar_op[is_item](x, item) for x in i)))
        return self.__append((is_item, item))

    def __getattr__(self, item):
        return self.__get(item, False)

    def __getitem__(self, item):
        return self.__get(item, True)

    # SUM
    def __sum(self, obj, value=none):
        for optic in self:
            try:
                v = optic(obj)
                if value is none:
                    return v
                return optic(obj, value)
            except:
                continue
        raise TypeError

    def __compose(self, other, T):
        if not isinstance(other, type(self)):
            other = type(self)((0, other))
        if self.__T == T:
            return self.__append(other)
        return type(self)((T, self, other))

    def __add__(self, other):
        return self.__compose(other, 2)

    def __radd__(self, other):
        return type(self)(0, other) + self

    # PRODUCT
    def __product(self, obj, value=none):
        return tuple(optic(obj, value) for optic in self.__items)

    def __mul__(self, other):
        return self.__compose(other, 3)

    def __rmul__(self, other):
        return type(self)(0, other) * self


    # EXPONENTIAL
    def __exponential(self, obj, value=none):
        _, optic = self
        return tuple(optic(x, value) for x in obj)

    def __invert__(self):
        return type(self)((4, self))

    # REDUCE
    # def __div(self, obj, value=none):
    #     L, R = self.__items

    # def __truediv__(self, other):
    #     if not isinstance(other, type(self)):
    #         other = type(self)((0, other))
    #     return type(self)((5, self, other))

    # APPLY
    __handlers = (__const, __scalar, __sum, __product, __exponential)

    def __call__(self, obj=none, value=none):
        if self.__obj is none:
            if obj is none:
                raise ValueError('must pass object to unbound optic')
            return self.__handlers[self.__T](self, obj, value)
        return self.__handlers[self.__T](self, self.__obj, obj)

    # DESCRIPTOR
    def __get__(self, instance, owner):
        return self()

    def __set__(self, instance, value):
        return self(value)

    def __delete__(self, instance):
        return self(delete)


def view(obj=none, **kwargs):
    """
    Access a set of optics as members of an object.

    example:
    d = {'a':1}
    v = view(d, b=X['a'])
    print(v.b) # 1
    v.b = 3
    print(d) # {'a':3}
    """
    repr_o = '' if obj is none else f'obj={repr(obj)}, '
    return type('view', (), dict(
        {k: v if obj is none else v << obj for k, v in kwargs.items()},
        __repr__=lambda s:f'view({repr_o}**{repr(kwargs)})',
    ))()


X = Optic((1,))


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
