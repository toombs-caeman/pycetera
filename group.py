import collections
import functools
import itertools
import unittest
import types


def derived(type_, also_wrap=None):
    """
    construct a derived type that wraps all methods of the base
    so that those functions return the instance type when they would return the base

    currently only works if the constructor for the derived type accepts
    the base instance as its sole argument
    """
    # default values
    if also_wrap is None:
        also_wrap = {}

    # components of the type
    name = 'derived_{}'.format(type_.__name__)
    bases = (type_,)
    body = {}

    def wrap(_m):
        def method_wrapper(self, *args, **kwargs):
            # call to the derived type's method
            ret = getattr(type_, _m)(self, *args, **kwargs)
            if isinstance(ret, type_):
                # wrap as the type of self
                return type(self)(ret)
            # otherwise try to wrap other types
            return also_wrap.get(type(ret), lambda x:x)(ret)

        return method_wrapper

    # wrap all methods of the derived type
    for m in dir(type_):
        attr = getattr(type_, m)
        if isinstance(
                attr,
                (
                        types.FunctionType,
                        types.WrapperDescriptorType,
                        types.MethodDescriptorType,
                )
        ):
            body[m] = functools.wraps(attr)(wrap(m))
    # construct and return the type
    return type(name, bases, body)


class Group:
    def __call__(self, f):
        """Map a function over this group."""
        return type(self)(map(f, self))

    def __getitem__(self, item):
        """apply one or more filters over this group."""
        if isinstance(item, tuple):
            return type(self)(map(lambda x: self[x], item))
        if callable(item):
            return type(self)(filter(item, self))
        raise TypeError("couldn't filter on " + str(item))

    # FUNCTOOLS/ITERTOOLS SUGAR
    @functools.wraps(functools.reduce)
    def reduce(self, f, initial=None):
        return functools.reduce(f, self, initial)

    @functools.wraps(itertools.groupby)
    def groupby(self, key=None):
        return type(self)(itertools.groupby(self, key=key))

    @functools.wraps(itertools.chain)
    def chain(self, *i):
        return type(self)(itertools.chain(self, *i))

    @functools.wraps(zip)
    def zip(self, *i):
        return type(self)(zip(self, *i))

    @functools.wraps(itertools.zip_longest)
    def zip_longest(self, *i, fillvalue=None):
        return type(self)(itertools.zip_longest(self, *i, fillvalue=fillvalue))

    @functools.wraps(itertools.cycle)
    def cycle(self):
        return type(self)(itertools.cycle(self))

    @functools.wraps(itertools.tee)
    def tee(self, n=2):
        return Tuple(map(Iter, itertools.tee(self, n=n)))

    @functools.wraps(itertools.repeat)
    def repeat(self, times=None):
        return type(self)(itertools.repeat(self, times=times))

    # TYPE CONVERSION
    def iter(self):
        return Iter(self)

    def set(self):
        return Set(self)

    def list(self):
        return List(self)

    def tuple(self):
        return Tuple(self)


class OrderedGroup(Group):
    """A lightweight list class that provides extended map and filter syntax."""

    def __getitem__(self, item):
        try:
            return Group.__getitem__(self, item)
        except TypeError:
            # get the next super type after group
            mro = type(self).__mro__
            s = mro[mro.index(Group) + 1]
            return s.__getitem__(self, item)


class Iter(Group):

    def __init__(self, i):
        self.iter = iter(i)
        while isinstance(self.iter, Iter):
            self.iter = self.iter.iter

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.iter)

    def __getitem__(self, item):
        """apply one or more filters over this group."""
        return type(self)(filter(item, self))


class List(OrderedGroup, derived(list)):
    """A lightweight list class that provides extended map and filter syntax."""
    def join(self, sep=''):
        return Str(sep.join(self))

class Str(derived(collections.UserString, {list:List})):
    def print(self):
        print(self)


class Tuple(OrderedGroup, derived(tuple)):
    """A lightweight tuple class that provides extended map and filter syntax."""


class Set(Group, derived(set)):
    """A lightweight set class that provides extended map and filter syntax."""

    @functools.wraps(sorted)
    def sort(self, key=None, reverse=False):
        return List(sorted(self, key=key, reverse=reverse))


class TestList(unittest.TestCase):
    def setUp(self):
        self.g = List(range(10))
        self.s = List(('', '{}', 'ump', 'hello {}!', 'wazzup home {}'))
        # common functions
        self.lambdas = [
            (lambda x: x * 5),
            (lambda x: x + x),
        ]
        # int functions
        self.g_lambdas = [
            (lambda x: x % 3),
            (lambda x: x / 3.5),
            *self.lambdas
        ]
        # string functions
        self.s_lambdas = [
            (lambda x: x.format(3)),
            *self.lambdas
        ]

    def test_map(self):
        for l in self.g_lambdas:
            self.assertEqual(self.g(l), list(map(l, self.g)))
        for l in self.s_lambdas:
            self.assertEqual(self.s(l), list(map(l, self.s)))

    def test_filter(self):
        for l in self.g_lambdas:
            self.assertEqual(self.g[l], list(filter(l, self.g)))
            self.assertEqual(self.g[l, 3], [list(filter(l, self.g)), list(self.g)[3]])
        for l in self.s_lambdas:
            self.assertEqual(self.s[l], list(filter(l, self.s)))
            self.assertEqual(self.s[l, 3], [list(filter(l, self.s)), list(self.s)[3]])
        self.assertEqual(self.g[4, 7::-1], [list(self.g)[4], list(self.g)[7::-1]])

    @unittest.skip
    def test_reduce(self):
        self.fail("TODO")


if __name__ == '__main__':
    unittest.main()
