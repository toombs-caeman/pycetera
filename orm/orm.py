import logging
import unittest
import datetime
import sqlite3 as sql
from functools import lru_cache

log = logging.getLogger(__name__)
HAL = "I'm sorry Dave, I'm afraid I can't do that."

def record(names, defaults=()):
    """Like collections.namedtuple but mutable."""
    class _:
        def __init__(self, *args, **kwargs):
            # names are resolved first in kwargs, then args, then defaults
            args = list(args[::-1])
            object.__setattr__(
                self, "__fields",
                {
                    n: kwargs.get(n, args.pop() if args else defaults[i - len(names)])
                    for i, n in enumerate(names)
                },
            )

        def __iter__(self):
            return iter(self.__fields.values())

        def __getattr__(self, item):
            return self.__fields[item]

        def __repr__(self):
            return repr(self.__fields)
    return _


def explain(query, params):
    return query.replace("?", "{!r}").format(*params)


### TYPE HANDLING ###
TYPES = {
    "null": None,
    "integer": int,
    "real": float,
    "text": str,
    "blob": bytes,
    "date": datetime.date,
    "timestamp": datetime.datetime,
}
TYPES.update({v: k for k, v in TYPES.items()})


def register_type(sql_name, python_cls):
    TYPES[sql_name] = python_cls
    TYPES[python_cls] = sql_name

class Row(sql.Row):
    def __getattr__(self, item):
        return self[item]

### END TYPE HANLDING ###

### DATABASE ###
class Database:
    """
    A time-series semi-ORM inspired by django
    """

    def __init__(self, database=':memory:', **kwargs):
        self._options = {
            "database": database,
            **kwargs,
        }
        with self.conn as conn:
            log.info("checking db '%s'...", database)
            for model in Model.__subclasses__():
                # models that start with '_' are considered abstract
                if model.__name__.startswith('_'): continue

                log.info("checking model '%s'...", model.__name__)
                # give the model this db so that they can create connections
                model._db = self

                field_names = [f.name for f in model._fields]

                columns = conn.execute(f"pragma table_info({model.__name__})").fetchall()
                column_names = [c.name for c in columns]

                # if the table doesn't exist then create it
                if not columns:
                    # create table from model
                    log.info(f"creating table '%s'...", model.__name__)
                    conn.execute(*model._render)
                    continue

                # make sure the schema matches what we've got in python
                needs_migration = False
                for col in columns:
                    if col.name not in field_names:
                        needs_migration = True
                        break

                    field = getattr(model, col.name)
                    # TODO set needs_migration if col flags don't match

                if needs_migration:
                    log.warning("migrating table '%s'...", model.__name__)
                    # move the table to temporary location
                    conn.execute(f"alter table {model.__name__} rename to {model.__name__}_old")
                    # recreate the table
                    conn.execute(*model._render)
                    # TODO move all the data
                    conn.execute(f"drop table {model.__name__}_old")
                    continue

                # if the field doesn't have a matching column it needs to be added
                for field in model._fields:
                    if field.name in column_names:
                        continue
                    log.info("adding field '%s' to table '%s'", field.name, model.__name__)
                    self.add_column(model, field)

        log.info("%s ok", database)

    def add_column(self, model, field):
        raise NotImplementedError

    @property
    def conn(self):
        conn = sql.connect(**self._options)
        conn.row_factory = Row
        conn.execute("pragma foreign_key = 1")
        return conn


### FIELD ###

# Foreign key flags
Restrict = "restrict"
SetNull = "set null"
SetDefault = "set default"
Cascade = "cascade"


# TODO python>=3.8 can be greatly simplified by namedtuple having 'default' parameter
class F(
    record(
        ["type", "default", "primary_key", "not_null", "on_delete", "on_update", "generate", "stored", "name"],
        [             None,         False,      False,          "",          "",         "",    False,   None],
    )
):
    @property
    def _render(self):
        """Return field definition"""
        out = f'{self.name} {TYPES.get(self.type, self.type.__name__)}'

        if self.not_null:
            out += ' not null'

        if self.primary_key:
            out += ' primary key'

        if self.generate:
            out += f' as {self.generate}'
            if self.stored:
                out += ' stored'
        elif self.default is not None:
            t = type(self.default)
            def_string = sql.adapters.get((t, sql.PrepareProtocol), str)(self.default)
            out += f" default ('{def_string}')"

        if issubclass(self.type, Model):
            out += f', foreign key ({self.name}) references {self.type.__name__}(id)'
            if self.on_update:
                out += f' on update {self.on_update}'
            if self.on_delete:
                out += f' on delete {self.on_delete}'
        return out, ()

### END FIELD ###

### MODEL ###
class _model_meta(type):
    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def _fields(cls):
        fields = []
        # use dict comprehension to de-duplicate keys
        # don't use dir b/c we don't want to sort keys
        for k, v in {k:v for scls in reversed(cls.__mro__) for k, v in scls.__dict__.items()}.items():
            if isinstance(v, F):
                fields.append(F(*v, name=k))
                setattr(cls, k, fields[-1])
        return tuple(fields)

    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def row(model):
        class _(record(*zip(*((f.name, f.default) for f in model._fields)))):
            def __getattr__(self, item):
                value = self.__fields[item]
                # handle foreign keys
                fk = getattr(model, item)
                if issubclass(fk.type, Model):
                    return fk.type.get(id=value)
                return value

            def __setattr__(self, key, value):
                # handle foreign keys
                fk = getattr(model, key, None)
                if fk and issubclass(fk.type, Model) and isinstance(value, fk.type.row):
                    value = value.id

                self.__fields[key] = value

            def delete(self):
                # TODO
                raise NotImplementedError

            def save(self):
                render = f"insert into {model.__name__} values ({', '.join(f':{f.name}' for f in model._fields)})"
                # TODO inserting all into the first field??
                with model._conn as conn:
                    conn.execute(render, self.__fields)

        _.__name__ = model.__name__ + "_row"
        return _


    @property
    def _render(cls):
        f, d = zip(*(f._render for f in cls._fields))
        return f"create table {cls.__name__} ({', '.join(f)});", tuple(x for i in d for x in i)

    @property
    def _conn(cls):
        conn = cls._db.conn
        conn.row_factory = lambda c, r:cls.row(*r)
        return conn







class Model(object, metaclass=_model_meta):
    """
    A base class representing a queryset/instance.

    The class itself has meta-data of the table.
    an instance has information to construct a query.
    """
    id = F(int, primary_key=True, not_null=True)

    def __init__(self, **filters):
        self.filters = filters

    def __call__(self, **filters):
        return type(self)(**self.filters, **filters)

    @property
    def _render(self):
        # render where clause
        lookups = {
            "eq": "=",
            "gt": ">",
            "lt": "<",
            "ge": ">=",
            "le": "<=",
            "ne": "<>",
        }
        clauses = []
        for f in self.filters:
            field, *lookup = f.split("__")
            clauses.append(" ".join((field, *(lookups[l] for l in lookup or ["eq"]),"?")))

        # final render
        return f"select * from {type(self).__name__} where {' and '.join(clauses) or 1}", tuple(self.filters.values())

    def __iter__(self):
        return type(self)._conn.execute(*self._render)

    def all(self):
        return iter(self).fetchall()
    def delete(self):
        """return a count of deleted objects."""
        raise NotImplementedError

    def update(self, **fields):
        """return a count of updated objects."""
        T = type(self)
        return (
            f"insert into {T.__name__} values ({', '.join(['?'] * len(T._fields))})",
            [getattr(self, f.name) for f in T._fields]
        )

    def get(self, **filters):
        """
        fetch a single row if it exists.

        filters with a lookup are ignored (including '__eq') but others are used as field values.
        """
        """return a single Row or raise an exception."""
        items = iter(self(**filters) if filters else self).fetchmany(2)
        if len(items) != 1:
            # TODO better error here?
            raise sql.ProgrammingError
        return items[0]

    def create(self, **filters):
        """

        """
        new = type(self).new(
            **{
                k:v
                for k,v in {**self.filters, **filters}.items()
                if not k.contains("__")
            }
        )
        new.save()
        return new

    def get_or_create(self, **filters):
        return self.get(**filters) or self.create(**filters)


### END MODEL ###

class TestCase(unittest.TestCase):
    db = "test.db"

    def setUp(self):
        with sql.connect(self.db) as conn:
            for r in conn.execute("select name from sqlite_master where type='table'"):
                conn.execute(f"drop table {r[0]}")

    def test_render_field(self):
        self.assertEqual(
            ("name text", ()),
            F(str, name="name")._render,
        )

        self.assertEqual(
            ("name text not null default ('bruh')", ()),
            F(str, name="name", default='bruh', not_null=True)._render,
        )

    def test_render_model(self):
        na = "NA"

        class Artist(Model):
            first_name = last_name = F(str, na)
            birthday = F(datetime.date, datetime.date(1000, 1, 1), not_null=True)

        db = Database(self.db)
        self.assertEqual(
            ("create table Artist ("
             "id integer not null primary key, "
             "first_name text default ('NA'), "
             "last_name text default ('NA'), "
             "birthday date not null default ('1000-01-01'));", ()),
            Artist._render,
        )
        self.assertEqual(
            [
                (0, 'id', 'integer', 1, None, 1),
                (1, 'first_name', 'text', 0, repr(na), 0),
                (2, 'last_name', 'text', 0, repr(na), 0),
                (3, 'birthday', 'date', 1, "'1000-01-01'", 0),
            ],
            [tuple(r) for r in db.conn.execute("pragma table_info(artist)").fetchall()],
        )

    def test_select(self):
        class Artist(Model):
            first_name = last_name = F(str)

        Database(self.db)


if __name__ == '__main__':
    unittest.main()
