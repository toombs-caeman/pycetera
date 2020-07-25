import abc
import unittest
import operator

# see also https://python-lenses.readthedocs.io/en/latest/tutorial/optics.html
# TODO
# TODO problems:

"""
* explain syntax: + * >> [] .attr
* making a setter could be an expensive operation since it creates a whole new object.
    perhaps change to __call__(self, obj, values=None) instead of using the rshift operator
* branch selection bug in prism
* be sure to consume greedily if setters are used
* __pow__ for map over values
"""


def explain(optic, obj=None, values=None):
    """Like repr() but return the equivalent non-optic expression."""
    return optic.__explain__(obj)


class _Optic(abc.ABC):
    @abc.abstractmethod
    def __call__(self, obj, values=None):
        """
        Apply the Optic to an object.

        If values is provided, set the values and return the old
        otherwise just get the values.
        """

    @abc.abstractmethod
    def __repr__(self):
        """Return the optics syntax that describes this expression."""

    @abc.abstractmethod
    def __explain__(self, obj=None, values=None):
        """
        Like __repr__ but return the equivalent non-optic expression.

        If obj is None, return the equivalent lambda
        otherwise show the expression that would result from calling self(obj)

        explain(X) <=> 'lambda x:x'
        explain(X, 3) <=> '3'
        """



class _PseudoOptic(_Optic):
    """Wrap constant values as an Optic."""

    def __init__(self, value):
        self.__value = value

    def __call__(self, *_args, **_kwargs):
        return self.__value

    def __repr__(self):
        return repr(self.__value)

    def __explain__(self, *_args, **_kwargs):
        return str(self.__value)


class Optic(_Optic, tuple, abc.ABC):

    def __mul__(self, other):
        """
        Combine Optics into a product type (Spectra).
        """
        return self.__combine(other, Spectra)

    def __rmul__(self, other):
        return Lens(_pre=_PseudoOptic(other)) * self

    def __add__(self, other):
        """Combine Optics into a sum type (Prism)."""
        return self.__combine(other, Prism)

    def __radd__(self, other):
        return Lens(_pre=_PseudoOptic(other)) + self

    def __invert__(self):
        """Convert Optic into a map type (Map)."""
        return Map(self)

    def __getitem__(self, item):
        return Lens(_pre=self)[item]

    def __getattr__(self, item):
        return getattr(Lens(_pre=self), item)

    def __combine(self, other, T):
        if not isinstance(other, Optic):
            other = Lens(_pre=_PseudoOptic(other))
        if isinstance(self, T):
            if isinstance(other, T):
                return T(tuple(self) + tuple(other))
            return T(tuple(self) + (other,))
        if isinstance(other, T):
            return T((self,) + tuple(other))
        return T((self, other))


class Lens(Optic):
    """
    Generate getter and setter functions.

    equiv:
    X <=> lambda x:x

    The examples given here show a lens expression (with X=Lens()) on the left
    and their equivalent lambda expression on the right. Lens expressions are composable.
    examples:
    X = Lens()
    X.attr      # lambda x:x.attr               # get attributes
    X[3]        # lambda x:x[3]                 # get items
    X**(5,4)    # lambda x:x(5,4)               # call methods
    X.foo >> 3  # lambda x:setattr(x,'foo',3)   # set attributes, also works for items
    """
    __ops = (operator.getitem, getattr, operator.setitem, setattr)
    __fmt = ("[{}]", ".{}", "[{}] >> {}", ".{} >> {}")

    def __init__(self, _tuple=(), *, _pre=None):
        super().__init__()
        self.__pre = _pre

    def __call__(self, obj, values=None):
        def apply(o):
            if not self:
                return o
            *t, (f, i) = self
            for f, i in t:
                o = self.__ops[f](o, i)
            if values:
                return self.__ops[f + 2](o, i, values)
            return self.__ops[f](o, i)

        if self.__pre:
            obj = self.__pre(obj)
            if isinstance(self.__pre, Spectra):
                return map(apply, obj)
        return apply(obj)

    def __repr__(self):
        return "{}{}".format(
            f"({repr(self.__pre)})" if self.__pre else "Lens()",
            "".join(self.__fmt[f].format(i) for f, i in self),
        )

    def __explain__(self, obj=None, values=None):
        # base
        base = '' if obj else "lambda x:"

        # body
        body = str(obj) if obj else 'x'
        if not self:
            return base + body
        *t, (f, i) = self
        tail = "".join(self.__fmt[f].format(i) for f, i in (t if f > 1 else self))

        # __pre
        if isinstance(self.__pre, Spectra):
            body = f'map(lambda y:y{tail}, {explain(self.__pre, body)})'
        else:
            body = f'{explain(self.__pre, body) if self.__pre else body}{tail}'

        if values is None:
            return base + body

        # setters
        return "{}({}, {}, {})".format(
            base + self.__ops[f].__name__,
            body,
            repr(i),
            repr(values),
        )


    def __getitem__(self, item):
        return type(self)(tuple(self) + ((0, item),), _pre=self.__pre)

    def __getattr__(self, item):
        return type(self)(tuple(self) + ((1, item),), _pre=self.__pre)


class Prism(Optic):
    """
    The sum type.

    explain() of a Prism uses the pseudo-function oneof() which behaves roughly like below.
    This is done because it uses try..catch blocks, which are statements and cannot be included in a lambda

    def oneof(*callables):
        def func(operand):
            for f in callables:
                try:
                    return f(operand)
                except:
                    continue
            raise TypeError
        return func

    example:
    X.foo+X[0]  # lambda x:x.foo if hasattr(x, 'foo') else x[0]
    """

    def __call__(self, obj, values=None):
        for optic in self:
            try:
                v = optic(obj)
                if values is None:
                    return v
                return optic(obj, values)
            except:
                continue
        raise TypeError('Prism does not match object')

    def __repr__(self):
        return " + ".join(repr(o) for o in self)

    def __explain__(self, obj=None):
        return f'oneof({", ".join(explain(o) for o in self)}){f"({obj})" if obj else ""}'


class Spectra(Optic):
    """
    The product type, typically called a Traversal.

    example:
    X.foo*X.bar*X[2]    # lambda x:(x.foo, x.bar, x[2])
    """

    def __call__(self, obj, values=None):
        if values is None:
            return (optic(obj) for optic in self)
        if len(values) != len(self):
            raise ValueError('Spectra length does not match argument length')
        return list(optic(obj, val) for optic, val in zip(self, values))

    def __repr__(self):
        return " * ".join(repr(x) for x in self)

    def __explain__(self, obj=None, values=None):
        if values:
            if len(values) != len(self):
                raise ValueError('Spectra length does not match argument length')
            inner = ", ".join(explain(x, obj or "s", v) for x,v in zip(self, values))
        else:
            inner = ", ".join(explain(x, obj or "s") for x in self)
        return f'{"" if obj else "lambda s:"}({inner})'


class Map(Optic):
    """Apply an Optic to each element of a sequence."""

    def __init__(self, _tuple=()):
        self.__type = type(_tuple)

    def __call__(self, obj, values=None):
        if values is None:
            return map(self.__type(self), obj)
        return list(map(self.__type(self), obj, values))

    def __repr__(self):
        return f"~({repr(self.__type(self))})"

    def __explain__(self, obj=None, values=None):
        v = "" if values is None else f", {values}"
        if obj:
            return f'map({explain(self.__type(self))}, {obj}{v})'
        return f'lambda i: map({explain(self.__type(self))}, i{v})'


# A Lens to use as the common starting point for external use.
X = Lens()



def view(_obj, **kwargs):
    props = {k: lambda s, *a: v(s._obj, *a) for k, v in kwargs.items()}
    props = {k: property(v, v) for k, v in props.items()}
    props.update(_obj=_obj, __slots__=[])
    return type('view', (), props)()


class Test:
    a = 3

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
        X.foo(self.nonce, s)
        self.assertEqual(s, self.nonce.foo)

        # setitem
        X[0](self.nonce, 1)
        self.assertEqual(
            1,
            self.nonce[0],
        )

    def test_map(self):
        self.assertEqual(
            list((~X["color"])(self.json)),
            list(map(X["color"], self.json)),
        )

    def test_spectra(self):
        out = tuple((X[0] * X[3:5])(self.json))
        self.assertEqual(out, (self.json[0], self.json[3:5]))

    def test_prism(self):
        L = ~(X["value"] + X["color"])
        self.assertEqual(
            list(L(self.json)),  # list(map(lambda x: x.get('value', x.get('color')), self.json))
            ['#f00', 'green', '#00f', '#0ff', '#f0f', '#ff0', '#000']
        )
        L(self.json, ['foo'] * 7)
        self.assertEqual(
            list(map(X["value"] + X["color"], self.json)),
            ['foo'] * 7,
        )
        self.assertEqual([
            {"color": "red", "value": "foo"},
            {"color": "foo"},
            {"color": "blue", "value": "foo"},
            {"color": "cyan", "value": "foo"},
            {"color": "magenta", "value": "foo"},
            {"color": "yellow", "value": "foo"},
            {"color": "black", "value": "foo"}
        ],
            self.json
        )

        L(self.json, range(7))
        self.assertEqual([
            {"color": "red", "value": 0},
            {"color": 1},
            {"color": "blue", "value": 2},
            {"color": "cyan", "value": 3},
            {"color": "magenta", "value": 4},
            {"color": "yellow", "value": 5},
            {"color": "black", "value": 6}
        ],
            self.json
        )

    def test_opt(self):
        self.assertEqual(None, (X[99] + None)(self.json))
        self.assertEqual(self.nonce, (X[99] + self.nonce)(self.json))


if __name__ == '__main__':
    unittest.main()
