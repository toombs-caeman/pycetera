import unittest
import collections
import datetime
import sqlite3 as sql
from functools import lru_cache

"""
the Worst Object-Relational Mapping (WORM)

"works" with a sqlite backend

TODO
* fix up default value handling. I'm inclined to handle it entirely python side
    since sqlite3's converter/adapter handling is attrocious.
* wrap/fix up converter/adapter/TYPES handling
"""

def explain(query, params):
    return query.replace("?", "{!r}").format(*params)


class Row(sql.Row):
    def __getattr__(self, item):
        return self[item]

    __repr__ = tuple.__repr__
    __str__ = tuple.__str__

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
            for model in self.all_models:
                # give the model this db so that they can create connections
                model._db = self

                field_names = [f.name for f in model._fields]

                columns = conn.execute(f"pragma table_info({model.__name__})").fetchall()
                column_names = [c.name for c in columns]

                # if the table doesn't exist then create it
                if not columns:
                    # create table from model
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
                    # TODO
                    self.add_column(model, field)

    def add_column(self, model, field):
        raise NotImplementedError

    @property
    def conn(self):
        conn = sql.connect(**self._options)
        conn.row_factory = Row
        conn.execute("pragma foreign_key = 1")
        return conn

    @property
    def all_models(self):
        for model in Model.__subclasses__():
            # models that start with '_' are considered abstract
            if model.__name__.startswith('_'): continue
            yield model


### FIELD ###

# Foreign key flags
Restrict = "restrict"
SetNull = "set null"
SetDefault = "set default"
Cascade = "cascade"


class F(collections.namedtuple(
    "Field",
    (
            "type", "default", "primary_key", "not_null",
            # foreign key fields
            "on_delete", "on_update",
            # generated exression
            "generate", "stored",
            "name",
    )
)):

    def __new__(
            cls,
            type, default=None, primary_key=False, not_null=False,
            *,
            on_delete="", on_update="",
            generate="", stored=False,
            name=None,
    ):
        return super().__new__(
            cls, type, default, primary_key, not_null, on_delete, on_update, generate, stored, name
        )

    @property
    def _render(self):
        """Return field definition"""
        out = ""
        if issubclass(self.type, Model):
            out += f'foreign key ({self.name}) references {self.type.__name__}(id)'
            if self.on_update:
                out += f' on update {self.on_update}'
            if self.on_delete:
                out += f' on delete {self.on_delete}'
        else:
            out += f'{self.name} {TYPES.get(self.type, self.type.__name__)}'

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

        return out, ()


### END FIELD ###

### MODEL ###
class _model_meta(type):
    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def _fields(cls):
        fields = []
        for k, v in cls.__dict__.items():
            if isinstance(v, F):
                v = v._replace(name=k)
                setattr(cls, k, v)
                fields.append(v)
        return tuple(fields)

    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def _type(cls):
        return type(
            cls.__name__,
            (sql.Row,),
            {
                "_save": lambda s: cls[cls.id == s.id].update(**s),
                "_delete": lambda s: cls[cls.id == s.id].delete(),
            }
        )

    @property
    def _render(cls):
        f, d = zip(*(f._render for f in cls._fields))
        return f"create table {cls.__name__} ({', '.join(f)});", tuple(x for i in d for x in i)


class Model(object, metaclass=_model_meta):
    """
    A base class representing a queryset/model.

    The class itself has meta-data of the table.
    an instance has information to construct a query.
    """
    id = F(int, primary_key=True)

    # internal data
    _db = None

    def __init__(self, action="select"):
        pass

    @property
    def _render(self):
        return f"select id, * from {self.__name__} where {' and '.join(self.where)}"
        pass

    def __iter__(self):
        return self._db.conn.execute(*self._render)

    def _values(self, *fields):
        """return a model with additional clauses"""

    def _filter(self, **kwargs):
        """return a model with additional clauses"""

    def _get(self, **kwargs):
        """return a single Row or raise an exception."""
        return iter(self).fetchone()

    def get_or_create(self, **kwargs):
        """return a single Row or raise an exception."""

    def update(self, **kwargs):
        """return a count of updated objects."""

    def delete(self):
        """return a count of deleted objects."""

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
            ("create table Artist (first_name text default ('NA'), "
             "last_name text default ('NA'), "
             "birthday date not null default ('1000-01-01'));", ()),
            Artist._render,
        )
        self.assertEqual(
            [
                (0, 'first_name', 'text', 0, repr(na), 0),
                (1, 'last_name', 'text', 0, repr(na), 0),
                (2, 'birthday', 'date', 1, "'1000-01-01'", 0),
            ],
            [tuple(r) for r in db.conn.execute("pragma table_info(artist)").fetchall()],
        )

    def test_select(self):
        class Artist(Model):
            first_name = last_name = F(str)


if __name__ == '__main__':
    unittest.main()
