# hyper functional
# only expressions
# inspiration http://blog.ezyang.com/2012/11/extremist-programming/
globals().update({
    "define":globals().__setitem__,
    "def_type":lambda name, base=(), body={}:define(name, type(name), base, body),
    "none":object(),
    "zip":lambda*i,fillvalue=none:(
        [fillvalue if x is none else x for x in v]
        for i in ((*(iter(x) for x in i),),)
        for v in iter(
            lambda:(
                lambda v:(any if fillvalue is none else all)(x is none for x in v)or v
            )([next(x, none) for x in i]),
            True,
        )
    ),
    "filter":lambda f,a:(i for i in a if f(i)),
    "map":lambda f, *a: (f(*a) for a in zip(*a)),
    "reduce":lambda function, sequence, initial=none:[
        acc.pop(0)
        for it in (iter(sequence),)
        for acc in ([next(it, none)if initial is none else initial, next(it, none)],)
        for _ in iter(lambda:acc[0], none)
        if acc[1] == none or acc.extend((function(acc.pop(0), acc.pop()), next(it, none)))
    ][0],
})

