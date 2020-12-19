import unittest
from inspect import signature, Parameter

"""
An experiment in generator expressions and lambdas

# reading tips
start reading at the first for..in clause, then down. Read the first line as a yield
```
chain = lambda *i: (
    item
    for it in i
    for item in it
)
```
becomes
```
def chain(*i):
    for it in i:
        for item in it:
            yield item
```



"""
none = object()  # sentinel object

### UTILITY ###
# repeat sequences
cycle = lambda it: (
    i
    for a in (tuple(it),)
    for _ in iter(int, 1)
    for i in a
)
chain = lambda *i: (
    item
    for it in i
    for item in it
)

partial = lambda f, *args, **kwargs: [
    F(*args, **kwargs)
    for s in (len([p for p in signature(f).parameters.values() if p.default == Parameter.empty]),)
    for F in (lambda *ar, **kw: f(*ar, **kw) if s <= len(ar) + len(kw) else lambda *a, **k: F(*ar, *a, **kw, **k),)
][0]



### FUNCTIONS ###

# act like zip_longest if fillvalue else like zip
zip = lambda *i, fillvalue=none: (
    # replace any errant nones with the proper fillvalue
    [fillvalue if x is none else x for x in v]
    # start by making sure we've got actual iterators
    for i in ([iter(x) for x in i],)
    # break when flag is set
    for v in iter(
    lambda: (
        # return True if we're done, otherwise the tuple of values
        lambda v: (any if fillvalue is none else all)(x is none for x in v) or v
        # here's where we do the actual zip, and fill in with none
    )([next(x, none) for x in i]),
    True,
)
)
filter = lambda f, a: (i for i in a if f(i))
reduce = lambda function, sequence, initial=none: [
    # return the final value and set the flag for the while loop
    acc.pop(0)
    # make sure we got an iterator
    for it in (iter(sequence),)
    # load acc with two values
    # really, acc[0] is the accumulator, and acc[1] is used as a flag
    for acc in ([next(it, none) if initial is none else initial, next(it, none)],)
    # while acc[0] != none:
    # while we technically have 3 for loops here, this is the only one that
    # potentially loops more than once.
    for _ in iter(lambda: acc[0], none)
    # 'or' short-circuits, so check our flag first
    # list.extend returns None, so we can just tack this on.
    if acc[1] == none or acc.extend((function(acc.pop(0), acc.pop()), next(it, none)))
][0]
map = lambda f, *a: (f(*a) for a in zip(*a))


class BaseTest:
    """Abstract base test to ensure we hit all the edge cases"""

    def test_empty(self):
        self.fail("Not Implemented")

    def test_one(self):
        self.fail("Not Implemented")

    def test_five(self):
        self.fail("Not Implemented")

    def test_chain(self):
        """pass an iterator, not a list"""
        self.fail("Not Implemented")


class Cycle(BaseTest, unittest.TestCase):
    def test_empty(self):
        cycle([])
        self.fail("Not Implemented")

    def test_one(self):
        self.fail("Not Implemented")

    def test_five(self):
        self.fail("Not Implemented")

    def test_chain(self):
        """pass an iterator, not a list"""
        self.fail("Not Implemented")


class Reduce(BaseTest, unittest.TestCase):
    pass


class Map(BaseTest, unittest.TestCase):
    pass


class Filter(BaseTest, unittest.TestCase):
    pass


class Zip(BaseTest, unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
