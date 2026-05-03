# interval math
# see https://pyinterval.readthedocs.io/en/latest/

# internally, a simple interval is a range
# because it supports __contains__

type _range = int | range | slice | Range


def _normalize(r: _range) -> range:
    match r:
        case range():
            return r
        case int():
            return range(r, r+1)
        case slice():
            return range(r.start, r.stop, r.step or 1)
        case _:
            raise ValueError(r)


class RangeMeta(type):
    def __getitem__(cls, v: _range | tuple[_range, ...]) -> 'Range':
        match v:
            case Range():
                return v
            case tuple():
                return Range(*map(_normalize, v))
            case _:
                return Range(_normalize(v))


class Range(metaclass=RangeMeta):
    """Range is frozenset[int] but represents things internally with ranges."""
    # TODO ducktype as frozenset

    def __init__(self, *intervals: _range):
        self.intervals: tuple[range, ...] = ()
        if not intervals:
            return
        ni = sorted(map(_normalize, intervals), key=lambda r: r.start)
        I = ni[:1]
        # TODO respect step
        for i in ni:
            if i.start <= I[-1].stop:
                # merge overlapping ranges
                I[-1] = range(
                    min(i.start, I[-1].start),
                    max(i.stop, I[-1].stop)
                )
            else:
                I.append(i)
        self.intervals = tuple(I)

    def __str__(self):
        return f"[{','.join(f'{s.start}:{s.stop}' for s in self.intervals)}]"

    def __repr__(self):
        return f"Range{self}"

    def __add__(self, other: _range):
        match other:
            case Range():
                # both intervals are sorted already
                return Range(*self.intervals, *other.intervals)
            case _:
                return Range(*self.intervals, other)

    def __iter__(self):
        for i in self.intervals:
            yield from i

    def __contains__(self, i: int):
        return any(i in r for r in self.intervals)
