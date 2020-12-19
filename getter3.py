import unittest
from functools import reduce as R
from roperator import *

"""
** SHORTENINGS **
t=type
i=isinstance
T=(tuple,)
R=functools.reduce

** VARS **
s: self
a: args (tuple)
k: kwargs (dictionary)
f: a function
l: a Lambda
o: a generic item
r: a record (tuple)

** FUNCTIONS **
e(l, *a): evaluate a lambda with the given arguments
a(l): determine the arrity of a lambda

** VALUES **
x,y: stand-in variables for the first and second position
F: compositor
"""
t,i=type,isinstance
T=tuple,
x=t("",T,{f'__{f.__name__}__':(lambda f:lambda s,*a,**k:t(s)((*s,(f,a,k))))(f)for f in(getitem,call,getattr,lt,le,eq,ne,ge,gt,add,radd,and_,rand,floordiv,rfloordiv,lshift,rlshift,matmul,rmatmul,mod,rmod,mul,rmul,or_,ror,pow,rpow,rshift,rrshift,sub,rsub,truediv,rtruediv,xor,rxor)})()
y,a,e=t("",(t(x),),{})(),lambda l:i(l,t(y))or any(a(l)for r in l for l in r[1]if i(l,t(x))),lambda l,*a:R(lambda l,r:r[0](l,*(e(l,*a)if i(l,t(x))else l for l in r[1]),**r[2]),l,a[i(l,t(y))])
F=t("",T,{"__call__":lambda s,l:t(s)((*s,(2,l)))if i(l,t(x))else R(lambda i,r:(filter,R,map)[r[0]](lambda*a:e(r[1],*a),i),s,l),"__getitem__":lambda s,l:t(s)((*s,(a(l),l)))})()


class Test(unittest.TestCase):
    def call(self, l, o):
        return list(F(l)(o))
    def get(self, l, o):
        return list(F[l](o))

    def test_eval(self):
        self.assertEqual(4, e(x+1, 3))
        self.assertEqual(4, e(x[0], [4]))
        self.assertEqual(4, e(x*y, 2, 2))

    def test_call(self):
        self.assertListEqual(
            [i+1 for i in range(10)],
            self.call(x+1, range(10)),
        )
        self.assertEqual(
            [i>1 for i in range(10)],
            self.call(x > 1, range(10)),
        )
    def test_get(self):
        self.assertEqual(
            [i for i in range(10) if i > 1],
            self.get(x > 1, range(10)),
        )
        self.assertEqual(
            F[x + y](range(10)),
            sum(range(10))
        )


if __name__ == '__main__':
    unittest.main()

