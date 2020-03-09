import unittest

def singleton(*a, **kw):
    def inner(klass):
        return klass(*a, **kw)

    return inner

def static_vars(**kw):
    def wrapper(f):
        for k, v in kw.items():
            setattr(f, k, v)
        return f
    return wrapper



class TestDecorators(unittest.TestCase):
    def test_static_vars(self):

        @static_vars(count=0)
        def counter():
            counter.count += 1
            return counter.count
        self.assertEqual(counter(), 1)
        self.assertEqual(counter(), 2)
        self.assertEqual(counter(), 3)

    def test_singleton(self):
        littleL = [3,5,3]
        @singleton(littleL)
        class BigL(list):
            pass
        self.assertTrue(isinstance(BigL, list))
        self.assertEqual(BigL, littleL)
        @singleton()
        def f():
            return 3
        self.assertEqual(f, 3)


if __name__ == '__main__':
    unittest.main()
