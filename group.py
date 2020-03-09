import functools
import unittest


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

    def reduce(self, f, i=None):
        return functools.reduce(f, self, i)

    def branch(self, condition, *branches, default=lambda x: x):
        return type(self)(
            (branches[branch] if 0 <= branch < len(branches) else default)(item)
            for branch, item
            in zip(self(condition), self)
        )


class OrderedGroup(Group):
    """A lightweight list class that provides extended map and filter syntax."""

    def __getitem__(self, item):
        try:
            return Group.__getitem__(self, item)
        except TypeError:
            # get the next super type after group
            mro = type(self).__mro__
            s = mro[mro.index(Group) + 1]
            if isinstance(item, slice):
                return type(self)(s.__getitem__(self, item))
            return s.__getitem__(self, item)

    def set(self):
        return Set(self)


class List(OrderedGroup, list):
    """A lightweight list class that provides extended map and filter syntax."""
    pass


class Tuple(OrderedGroup, tuple):
    """A lightweight tuple class that provides extended map and filter syntax."""
    pass


class Set(Group, set):
    """A lightweight set class that provides extended map and filter syntax."""

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

    def test_branch(self):
        l = self.g_lambdas[:2]
        self.assertEqual(
            self.g.branch(lambda x: x % 3, *l),
            [l[0](x) if x % 3 == 0 else l[1](x) if x % 3 == 1 else x for x in self.g],
        )


if __name__ == '__main__':
    unittest.main()
