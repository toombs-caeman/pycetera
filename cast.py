import collections
import unittest

from decorators import boundmethod


class cast:
    """
    Perform type casting based on registered functions.
    """
    registered = collections.defaultdict(dict)

    def __init__(self):
        self.registered = collections.defaultdict(dict)

    @boundmethod
    def register(self, f, from_type=None, to_type=None):
        a = {**f.__annotations__}
        to_type = to_type or a.pop('return')
        if from_type is None:
            from_type, *_ = a.values()

        self.registered[to_type][from_type] = f
        return f

    @boundmethod
    def cast(self, obj, to_type):
        if isinstance(obj, to_type):
            return obj

        for from_type, transform in self.registered[to_type].items():
            if isinstance(obj, from_type):
                return transform(obj)

        # check the default registration
        if isinstance(self, cast):
            return type(self).cast(obj, to_type)

        # default to just trying the conversion
        return to_type(obj)


def typed_property(x):
    return property(
        fget=getattr,
        fset=lambda o, n, v:setattr(o, n, cast.cast(v, x)),
        fdel=delattr,
    )

class TestCast(unittest.TestCase):
    def test_main(self):
        self.fail()


if __name__ == '__main__':
    unittest.main()
