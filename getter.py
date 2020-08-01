from operator import getitem, setitem, delitem

none = object()
delete = object()


def lens_property(getter, obj=none):
    getter = getter if obj is none else lambda _, v=none: getter(obj, v)
    return property(getter, getter, lambda x: getter(x, delete))


class Lens(tuple):
    """Combine the functionality of operator's itemgetter, attrgetter, and methodcaller."""
    __op = (
        getattr, getitem, lambda f, a, k: f(*a, **k),
        setattr, setitem,
        delattr, delitem,
    )
    __fmt = (
        ".{}".format,
        lambda x: f'[{repr(x)}]',
        lambda a, kw: f'._({", ".join((*map(repr, a), *(f"{k}={repr(v)}" for k,v in kw.items())))})'
    )

    def __repr__(self):
        return f'{type(self).__name__}(){"".join(self.__fmt[f](*i) for f, *i in self)}'

    def __getattr__(self, item):
        return type(self)(self + ((0, item),))

    def __getitem__(self, item):
        return type(self)(self + ((1, item),))

    def _(self, *args, **kwargs):
        return type(self)(self + ((2, args, kwargs),))

    def __call__(self, obj, value=none):
        if not self:
            return obj

        *t, (f, *i) = self

        if value is delete:
            if f == 2:
                raise SyntaxError("can't delete function call")
            f += 5
        elif value is not none:
            if f == 2:
                raise SyntaxError("can't assign to function call")
            f += 3
            i += (value,)

        for f, *i in t:
            obj = self.__op[f](obj, *i)
        return self.__op[f](obj, *i)


X = Lens()
