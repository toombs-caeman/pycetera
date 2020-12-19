from operator import *


def radd(b, a):
    "Same as a + b."
    return add(a, b)


def rand(b, a):
    "Same as a & b."
    return and_(a, b)


def rfloordiv(b, a):
    "Same as a // b."
    return floordiv(a, b)


def rlshift(b, a):
    "Same as a << b."
    return lshift(a, b)


def rmatmul(b, a):
    "Same as a @ b."
    return matmul(a, b)


def rmod(b, a):
    "Same as a % b."
    return mod(a, b)


def rmul(b, a):
    "Same as a * b."
    return mul(a, b)


def ror(b, a):
    "Same as a | b."
    return or_(a, b)


def rpow(b, a):
    "Same as a ** b."
    return pow(a, b)


def rrshift(b, a):
    "Same as a >> b."
    return rshift(a, b)


def rsub(b, a):
    "Same as a - b."
    return sub(a, b)


def rtruediv(b, a):
    "Same as a / b."
    return truediv(a, b)


def rxor(b, a):
    "Same as a ^ b."
    return xor(a, b)


def call(f, *args, **kwargs):
    "Same as f(*args, **kwargs)."
    return f(*args, **kwargs)

