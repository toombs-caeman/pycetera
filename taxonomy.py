from roperator import *

# a list of functions, implemented with magic methods, which must return a specific type.
coercing_operators = (len, bool, dir, format, repr, hash, str, int, contains,)
# a list of comparison operators as functions
comparison_operators = (eq, ge, gt, le, lt, ne)
# a list of functions representing syntax which is implemented with magic methods
# and can return any type.
non_coercing_operators = (
    *comparison_operators,
    # unary
    invert, neg, pos, index, iter, next, reversed,
    # reversible
    add, iadd, radd,
    and_, iand, rand,
    floordiv, ifloordiv, rfloordiv,
    lshift, ilshift, rlshift,
    matmul, imatmul, rmatmul,
    mod, imod, rmod,
    mul, imul, rmul,
    or_, ior, ror,
    pow, ipow, rpow,
    rshift, irshift, rrshift,
    sub, isub, rsub,
    truediv, itruediv, rtruediv,
    xor, ixor, rxor,
    # get/set/del
    getattr, setattr, delattr,
    getitem, setitem, delitem,
    call,
)
operators = (
    *coercing_operators,
    *non_coercing_operators,
)
