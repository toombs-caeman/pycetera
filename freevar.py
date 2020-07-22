import functools
import inspect
import unittest

from decorators import singleton
from operator import *


def as_(x):
    return x


attr = attrgetter
call = methodcaller


class rpartial(functools.partial):
    """exactly like functools.partial, but it reverses the order of supplied and enclosed positional arguments"""

    def __call__(*args, **keywords):
        if not args:
            raise TypeError("descriptor '__call__' of partial needs an argument")
        self, *args = args
        newkeywords = self.keywords.copy()
        newkeywords.update(keywords)
        return self.func(*args, *self.args, **newkeywords)


@singleton()
class X:
    """
    function composition interface

    add_mul = X.add(3).mul(4)
    add_mul(2) == (2+3) * 4
    add_mul.isinstance(int)(3) == isinstance((3+3)*4, int)

    add_mul2 = X.add(3).mul()
    add_mul2(2,5) == (2+3) * 5

    The constructor acts as a finite state machine (FSM) with two states and an append only queue
    Every call (X('asdf'), X['asdf'], or X.asdf) on an instance returns a new instance representing the next state.
    The instance itself pretends to be immutable.

    In state 0:
    * X[3] -> pushes itemgetter(3) to the queue
    * X.add -> tries to resolve the name 'add' to a callable
        then transitions to state 1 by setting flag=add
    * X(4) -> evaluates the queue with args=(4,) and returns the result.
        Note that this doesn't consume the queue or otherwise alter the state.

    In state 1:
    * X[3] -> raises an exception
    * X.add -> raises an exception
    * X(3) -> uses inspect.signature() to figure out how many arguments flag will accept (req)
        then pushes (req, rpartial(flag, 3)) onto the queue
        and finally transitions to state 0 by clearing flag

    queue evaluation treats its arguments as a stack (left is the top).
    Each pair (n_args, func) in the queue is processed by popping the n_args items off of the stack and passing them to
    func. The result of that call is pushed back on the stack (all python functions return a value or None).
    When the queue is exhausted, the top value of the stack is returned.

    """
    __slots__ = ["__queue", "__flag"]

    def __init__(self, *, queue=(), flag=None):
        self.__queue = queue
        self.__flag = flag

    def __delay__(self, func, *args, **kwargs):
        req = 1
        if func in (methodcaller, itemgetter, attrgetter):
            f = func(*args, **kwargs)
        else:
            f = rpartial(func, *args, **kwargs)
            try:
                req = len(inspect.signature(f).parameters)
            except ValueError:
                # some builtins don't have signatures
                pass
        return type(self)(queue=(*self.__queue, (req, f)))

    def __getitem__(self, item):
        if self.__flag:
            raise AttributeError()
        return self.__delay__(itemgetter, item)

    def __getattr__(self, item):
        if self.__flag:
            raise AttributeError()
        # try to find the name first from the calling frame, but default to this context
        frame = inspect.currentframe().f_back
        flag = eval(
            item,
            {**globals(), **frame.f_globals},
            {**locals(), **frame.f_locals},
        )

        if not callable(flag):
            raise NameError("callable '{}' not found".format(item))
        return type(self)(queue=self.__queue, flag=flag)

    def __call__(self, *args, **kwargs):
        if self.__flag:
            return self.__delay__(self.__flag, *args, **kwargs)

        def apply(stack, queue_pair):
            # each application pops n_args items off the stack and pushes back one
            n_args, func = queue_pair
            return (func(*stack[:n_args]), *stack[n_args:])

        return functools.reduce(apply, self.__queue, args)[0]


class TestLambda(unittest.TestCase):

    def test_lambda_map(self):
        g = list(range(10))
        self.assertEqual(list(map(X.gt(3), g)), [i > 3 for i in g])
        self.assertEqual(list(map(X.mul(3), g)), [i * 3 for i in g])
        self.assertEqual(list(map(X.pow(2), g)), [i * i for i in g])

    def test_lambda_filter(self):
        g = list(range(10))
        self.assertEqual(list(filter(X.gt(3), g)), [i for i in g if i > 3])
        self.assertEqual(list(filter(X.mod(2), g)), [i for i in g if i % 2])

    def test_lambda_reduce(self):
        self.assertEqual(functools.reduce(X.add(), range(10)), 45)
        self.assertEqual(functools.reduce(X.mul(), range(10)), 0)
        self.assertEqual(functools.reduce(X.add(), [1, 2, 3]), 6)

    def test_lambda_getattr(self):
        o = [type('', (), {"v": i})() for i in range(10)]
        self.assertEqual(list(map(X.attr('v'), o)), [i.v for i in o])
        pass

    def test_lambda_getitem(self):
        s = ('e{}', 'ump', 'hello {}!', 'wazzup home {}')
        self.assertEqual(list(map(X[1:], s)), [i[1:] for i in s])

    def test_emulations(self):
        _types = [1, 'a', 4.7]
        g = list(range(7, 10))
        s = ('{}', 'ump', 'hello {}!', 'wazzup home {}')
        self.assertEqual(list(filter(X.contains('h'), s)), [i for i in s if 'h' in i])
        self.assertEqual(list(map(X.mul(2.), g)), [i * 2. for i in g])
        self.assertEqual(list(map(X.isinstance(int), _types)), [isinstance(x, int) for x in _types])
        self.assertEqual(list(map(X.len(), s)), [len(i) for i in s])


if __name__ == '__main__':
    unittest.main()
