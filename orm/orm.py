import logging
import unittest
import datetime
import sqlite3 as sql
from functools import lru_cache

log = logging.getLogger(__name__)
# Foreign key flags
Restrict = "restrict"
SetNull = "set null"
SetDefault = "set default"
Cascade = "cascade"


class Database:
    class Row(sql.Row):
        def __getattr__(self, item):
            return self[item]

        def __repr__(self):
            return repr((*self,))

    @property
    def conn(self):
        conn = sql.connect(**self._options)
        conn.row_factory = self.Row
        conn.execute("pragma foreign_key = 1")
        return conn

    def __init__(self, database=':memory:', **kwargs):
        self._options = {"database": database, "detect_types": sql.PARSE_DECLTYPES, **kwargs}

        with self.conn as conn:
            log.info("initializing db '%s'...", database)
            all_models = {}

            # check definitions
            for model in Model.__subclasses__():
                # models that start with '_' are considered abstract
                if model.__name__.startswith('_'):
                    continue
                if model.__name__ in all_models:
                    msg = "duplicate definitions found for model '%s' in %s and %s" % (
                        model.__name__,
                        model.__module__,
                        all_models[model.__name__].__module__,
                    )
                    log.critical(msg)
                    raise ImportError(msg)
                all_models[model.__name__] = model

            for model in all_models.values():
                model._db = self

                field_names = [f.name for f in model._fields]
                columns = conn.execute(f"pragma table_info({model})").fetchall()
                column_names = [c.name for c in columns]

                # if the table doesn't exist then create it
                if not columns:
                    log.info(explain(*model._render))
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
                    log.warning("migrating table '%s'...", model)
                    raise NotImplementedError
                    # move the table to temporary location
                    conn.execute(f"alter table {model} rename to {model}_old")
                    # recreate the table
                    conn.execute(*model._render)
                    # TODO move all the data
                    conn.execute(f"drop table {model}_old")
                    continue

                # if the field doesn't have a matching column it needs to be added
                for field in model._fields:
                    if field.name in column_names:
                        continue
                    log.info("adding field '%s' to table '%s'", field.name, model)
                    raise NotImplementedError

        log.info("%s ok", database)


def explain(query, params):
    """Render a sql query"""
    if isinstance(params, dict):
        for k, v in params.items():
            query = query.replace(f':{k}', repr(v))
        return query
    return query.replace("?", "{!r}").format(*params)


def format_params(*args, **kwargs):
    j = ', '.join
    return j((*j(map(repr, args)), j(f'{k}={v!r}' for k, v in kwargs.items())))


def clean_dict(d):
    return {k: v.id if isinstance(v, _model_row) else v for k, v in d.items()}


def _named_list(*names, **defaults):
    """
    Like collections.namedtuple but mutable.

    Internally it is really a dict() which makes use of the fact that they are guaranteed insertion ordering.
    """
    names = (*names, *defaults)

    class _:
        def __init__(self, *args, **kwargs):
            args = list(reversed(args))
            object.__setattr__(self, "_fields", {})
            try:
                for n in names:
                    setattr(self, n, kwargs.pop(n) if n in kwargs else args.pop() if args else defaults[n])
            except KeyError:
                raise TypeError(f"Not enough arguments passed to {type(self)}.")
            if args or kwargs:
                raise TypeError(f"Extra arguments passed to {type(self)} ({format_params(*args, **kwargs)}).")

        def __iter__(self):
            return iter(self._fields.values())

        def __getattr__(self, item):
            return self._fields[item]

        def __setattr__(self, key, value):
            self._fields[key] = value

        def __eq__(self, other):
            return type(self) is type(other) and all(s == o for s, o in zip(self, other))

        def __ne__(self, other):
            return not self == other

        def _replace(self, **kwargs):
            return type(self)(**{**self._fields, **kwargs})

        def __repr__(self):
            return repr(self._fields)

    _.__name__ = "namedlist"
    return _


class Type:
    _types = {
        type(None): "NULL", int: "INTEGER", float: "REAL", str: "TEXT", bytes: "BLOB",
        datetime.date: "DATE", datetime.datetime: "TIMESTAMP",
    }

    @classmethod
    def register(cls, type, typename, converter, adapter):
        """
        register a new database type
        converter(bytes) -> object
        adapter(object) -> str, bytes, int, or float
        """
        cls._types[type] = typename
        sql.register_converter(typename, converter)
        sql.register_adapter(type, adapter)

    @classmethod
    def get_typename(cls, t):
        return f'INTEGER REFERENCES {t}' if issubclass(t, Model) else cls._types.get(t, cls._types[bytes])

    @classmethod
    def adapt(cls, o):
        # run any adapters, but not any converters, since it doesn't know how to convert the column
        return sql.connect(':memory:').execute('select ?', (o,)).fetchone()[0]


class Field(
    _named_list(
        "type",
        default=None, primary_key=False, not_null=False, on_delete="", on_update="", generate="", stored=False, name=""
    )
):
    @property
    def _render(self):
        return " ".join(
            value for condition, value in zip(
                (
                    self.name, self.type, self.on_delete, self.on_update, self.default,
                    self.primary_key, self.not_null, self.generate, self.stored
                ),
                (
                    self.name, Type.get_typename(self.type),
                    f'ON DELETE {self.on_delete}', f'ON UPDATE {self.on_update}',
                    f"DEFAULT ({Type.adapt(self.default)!r})",
                    "PRIMARY KEY", "NOT NULL", f'AS {self.generate}', "STORED",
                )
            ) if condition
        ), ()


class _model_row:
    pass


class _model_meta(type):
    def __str__(self):
        return self.__name__

    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def _fields(cls):
        fields = []
        # use dict comprehension to de-duplicate keys
        # don't use dir b/c we don't want to sort keys
        # TODO I don't think this allows overriding fields
        for k, v in {k: v for scls in cls.__mro__ for k, v in scls.__dict__.items()}.items():
            if isinstance(v, Field):
                fields.append(v._replace(name=k))
                setattr(cls, k, fields[-1])
        return tuple(fields)

    # decorators can be replaced by @functools.cached_property when sys.version >= 3.8
    @property
    @lru_cache(maxsize=None)
    def row(model):
        class model_row(_named_list(**{f.name: f.default for f in model._fields}), _model_row):
            def __getattr__(self, item):
                value = self._fields[item]
                # handle foreign keys
                fk = getattr(model, item)
                if isinstance(value, int) and issubclass(fk.type, Model):
                    self._fields[item] = fk.type.get(id=value)
                    return self._fields[item]
                return value

            def delete(self):
                if self.id:
                    render = f'DELETE FROM {model} WHERE id = :id'
                    with model._conn as conn:
                        log.info(explain(render, self._fields))
                        conn.execute(render, self._fields)
                    self.id = None
                    return True
                return False

            def save(self):
                render = (
                    f"INSERT INTO {model} VALUES ({', '.join(f':{f.name}' for f in model._fields)}) "
                    f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{f.name}=:{f.name}' for f in model._fields)} "
                    f"WHERE id=:id"
                )
                with model._conn as conn:
                    log.info(explain(render, clean_dict(self._fields)))
                    self.id = conn.execute(render, clean_dict(self._fields)).lastrowid
                return self

            def __eq__(self, other):
                # a row is also considered equal to its id
                return isinstance(other, int) and self.id == other or super().__eq__(other)

        model_row.__name__ = model.__name__ + "_row"
        return model_row

    @property
    def _render(cls):
        f, d = zip(*(f._render for f in cls._fields))
        return f"CREATE TABLE {cls} ({', '.join(f)});", tuple(x for i in d for x in i)

    @property
    @lru_cache(maxsize=None)
    def _conn(cls):
        conn = cls._db.conn
        conn.row_factory = lambda c, r: cls.row(*r)
        return conn

    @property
    def get(cls):
        return cls().get


class Model(object, metaclass=_model_meta):
    """
    A base class representing a queryset/instance.

    The class itself has meta-data of the table.
    an instance has information to construct a query.
    """
    id = Field(int, primary_key=True, not_null=True)

    def __init__(self, **filters):
        self.filters = filters

    def __call__(self, **filters):
        return type(self)(**self.filters, **filters)

    def __str__(self):
        return explain(*self._render)

    @property
    def _render(self):
        # render where clause
        cmp = {
            "eq": "=",
            "gt": ">",
            "lt": "<",
            "ge": ">=",
            "le": "<=",
            "ne": "<>",
            "in": "in",
        }
        clauses = []
        # lh, table,
        for filter, value in clean_dict(self.filters).items():
            # Album(artist__first_name__ne="joe")
            # select * from album where artist in (select id from artist where first_name <> "joe")
            # Song(album__artist__birthday__gt="date")
            # select * from song where album in (select id from album where artist in (select id from artist where birthday > "date"))
            clause = "{}"
            subq = "{} IN (SELECT id FROM {} WHERE {})"
            model = type(self)
            fields = filter.split("__")[::-1]
            op = cmp[fields.pop(0)] if fields[0] in cmp else "="
            # get
            while len(fields) > 1:
                field = fields.pop()
                model = getattr(model, field).type
                clause = clause.format(subq).format(field, model, "{}")
            clauses.append(clause.format(f'{fields.pop()} {op} :{filter}'))

        # final render
        return f"SELECT * FROM {type(self)} WHERE {' AND '.join(clauses) or 1}", clean_dict(self.filters)

    def __iter__(self):
        return type(self)._conn.execute(*self._render)

    def all(self):
        return iter(self).fetchall()

    def first(self):
        return iter(self).fetchone()

    def last(self):
        raise NotImplemented

    def delete(self):
        """return a count of deleted objects."""
        raise NotImplementedError

    def update(self, **fields):
        """return a count of updated objects."""
        T = type(self)
        return (
            f"insert into {T} values ({', '.join(['?'] * len(T._fields))})",
            [getattr(self, f.name) for f in T._fields]
        )

    def get(self, **filters):
        """
        fetch a single row if it exists.

        filters with a lookup are ignored (including '__eq') but others are used as field values.
        """
        items = iter(self(**filters) if filters else self).fetchmany(2)
        if len(items) != 1: raise ValueError("Multiple objects returned")
        return items[0]

    def create(self, **filters):
        # ignore fields with lookups
        return type(self).row(**{k: v for k, v in {**self.filters, **filters}.items() if not k.contains("__")}).save()

    def get_or_create(self, **filters):
        return self.get(**filters) or self.create(**filters)


class TestCase(unittest.TestCase):
    """Base """
    db = "test.db"

    def setUp(self):
        """Drop all tables before each test"""
        with sql.connect(self.db) as conn:
            for r in conn.execute("select name from sqlite_master where type='table'").fetchall():
                conn.execute(f"drop table {r[0]}")

    def initDatabase(self):
        return Database(self.db)


class ORMTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.basicConfig(level=logging.WARNING)

        class Artist(Model):
            first_name = last_name = Field(str, "NA")
            birthday = Field(datetime.date, datetime.date(1000, 1, 1), not_null=True)

        class Album(Model):
            artist = Field(Artist, not_null=True)
            title = Field(str, not_null=True)

        cls.artist = Artist
        cls.album = Album

    def test_namedlist(self):
        T = _named_list("a", "b", c=3, d=4)
        # test that arguments are correctly counted
        self.assertRaises(TypeError, T)
        self.assertRaises(TypeError, T, 1, 2, 3, 4, 5)
        self.assertRaises(TypeError, T, 2, 3, 4, 5, a=1)
        self.assertEqual([1, 2, 3, 4], [*T(1, 2)])
        self.assertEqual([1, 2, 3, 4], [*T(2, a=1)])

    def test_render(self):
        # field
        self.assertEqual(("name TEXT", ()), Field(str, name="name")._render)
        self.assertEqual(
            ("name TEXT DEFAULT ('bruh') NOT NULL", ()),
            Field(str, name="name", default='bruh', not_null=True)._render,
        )
        # table
        self.assertEqual(
            (f"CREATE TABLE {self.artist} ("
             "first_name TEXT DEFAULT ('NA'), "
             "last_name TEXT DEFAULT ('NA'), "
             "birthday DATE DEFAULT ('1000-01-01') NOT NULL, "
             "id INTEGER PRIMARY KEY NOT NULL);", ()),
            self.artist._render,
        )
        db = self.initDatabase()
        self.assertEqual(
            [
                (0, 'first_name', 'TEXT', 0, repr("NA"), 0),
                (1, 'last_name', 'TEXT', 0, repr("NA"), 0),
                (2, 'birthday', 'DATE', 1, "'1000-01-01'", 0),
                (3, 'id', 'INTEGER', 1, None, 1),
            ],
            [tuple(r) for r in db.conn.execute(f"pragma table_info({self.artist})").fetchall()],
        )
        id = db.conn.execute(
            "insert into artist(last_name) values ('Ni')"
        ).execute(
            "select * from artist where last_name ='Ni'"
        ).fetchone()
        self.assertEqual(
            "NA",
            id.first_name,
        )

    def test_select(self):
        first_name = "Mario"
        last_name = "Peach"
        self.initDatabase()
        self.artist.row(first_name, last_name).save()
        self.assertEqual(
            [f for f in self.artist.get(id=1)],
            [first_name, last_name, datetime.date(year=1000, month=1, day=1), 1],
        )

    def test_row(self):
        self.initDatabase()
        r = self.artist.row("Mike", "Goldblum")

        # insert
        self.assertEqual(r.id, None)
        r.save()
        self.assertEqual(r.id, 1)

        # update
        r.first_name = "Jeff"
        r.save()
        self.assertEqual(r.id, 1)
        self.assertEqual(len(self.artist().all()), 1)
        self.assertEqual(self.artist().first().first_name, "Jeff")

        r2 = self.artist.row("Do", "Little")
        r2.save()
        self.assertEqual(r2.id, 2)

        # delete
        r2.delete()
        self.assertEqual(r2.id, None)
        self.assertEqual(len(self.artist().all()), 1)
        self.assertEqual(self.artist().first().first_name, "Jeff")

    def test_foreign_key(self):
        db = self.initDatabase()
        artist = self.artist.row("Doja", "Cat").save()
        album = self.album.row(artist, "Hot Pink").save()
        self.assertEqual(album.artist.id, artist.id)
        self.assertEqual(album.artist.first_name, "Doja")

    def test_lookups(self):
        db = self.initDatabase()

        doja = self.artist.row("Doja", "Cat").save()
        hot_pink = self.album.row(doja, "Hot Pink").save()

        bd = datetime.date(1995, 10, 21)
        mushroom = self.artist.row("Infected", "Mushroom", bd).save()
        nasa = self.album.row(mushroom, "Head of NASA and the two Amish boys").save()
        shawarma = self.album.row(mushroom, "The Legend of the Black Shawarma").save()
        self.assertListEqual(
            [nasa, shawarma],
            self.album(artist=mushroom).all(),
        )
        self.assertEqual(
            [hot_pink],
            self.album(artist__birthday__ne=bd).all(),
        )

    @unittest.skip("not implemented")
    def test_dirty_check(self):
        # track if the row is dirty, and do a recursive save over foreign keys
        pass


if __name__ == '__main__':
    unittest.main()
