import collections
import unittest


class Caster:
    """
    Perform type casting based on registered functions.
    """

    def __init__(self, parent=None):
        self.parent = parent
        self.registered = collections.defaultdict(dict)

    def register(self, f, from_type=None, to_type=None):
        a = {**f.__annotations__}
        to_type = to_type or a.pop('return')
        if from_type is None:
            from_type, *_ = a.values()

        self.registered[to_type][from_type] = f
        return f

    def cast(self, obj, to_type):
        if isinstance(obj, to_type):
            return obj

        for from_type, transform in self.registered[to_type].items():
            if isinstance(obj, from_type):
                return transform(obj)

        # check the default registration
        if self.parent:
            return self.parent.cast(obj, to_type)

        # default to just trying the conversion
        return to_type(obj)


DefaultCaster = Caster()
register = DefaultCaster.register
cast = DefaultCaster.cast

Caster.__init__.__defaults__ = (DefaultCaster,)


class TestCast(unittest.TestCase):
    def setUp(self):
        global DefaultCaster
        DefaultCaster = Caster(None)

    def test_builtin(self):
        self.assertEqual(3, cast(3.5, int))
        t = list(range(3))
        self.assertEqual(tuple(t), cast(t, tuple))

    def test_register(self):
        c = Caster()
        funcType = type(lambda:None)

        register(lambda x:lambda:x, object, funcType)
        x = c.cast(None, funcType)
        self.assertIsNone(x())

        c.register(lambda x:lambda:3, object, funcType)
        x = c.cast(None, funcType)
        self.assertEqual(x(), 3)


if __name__ == '__main__':
    unittest.main()
