import logging
import unittest
from datetime import date, datetime
import sqlite3 as sql

log = logging.getLogger(__name__)
# Foreign key flags
Restrict = "restrict"
SetNull = "set null"
SetDefault = "set default"
Cascade = "cascade"


class Row(sql.Row):
    def __getattr__(self, item):
        return self[item]

    def __repr__(self):
        return repr((*self,))


def initialize_database(database="file::memory:?cache=shared", **options):
    options = {"database": database, "detect_types": sql.PARSE_DECLTYPES, "uri": True, **options}

    keep_alive = sql.connect(**options) if 'memory' in database else None

    def connect():
        keep_alive  # keep memory-only databases alive
        c = sql.connect(**options)
        c.execute("pragma foreign_key = 1")
        c.row_factory = Row
        return c

    def all_subclasses(cls):
        return {*cls.__subclasses__()}.union({c for s in cls.__subclasses__() for c in all_subclasses(s)})

    with connect() as conn:
        log.info(f"initializing database {database}")

        all_models = {}
        duplicates_found = False
        for model in all_subclasses(Model):
            name = str(model)
            if name.startswith('_'):
                continue  # models that start with '_' are considered abstract
            if name in all_models:
                duplicates_found = True
                log.critical(f"Duplicate model '{name}' in {model.__module__} and {all_models[name].__module__}")
            all_models[name] = model
        if duplicates_found:
            raise ImportError('Duplicate Model found.')

        sqlite_master._db = connect
        extant_tables = dict(sqlite_master(type='table')["name", "sql"])
        altered = False
        for name, model in all_models.items():
            model._db = connect

            if model._special:
                continue
            create_stmt = repr(model)
            if name not in extant_tables:
                log.info(create_stmt)
                conn.execute(create_stmt)
                altered = True
            elif create_stmt == extant_tables[name]:
                log.info(f"table {name} ok")
            else:
                # migrate table
                conn.execute(f"DROP TABLE IF EXISTS _{name}")
                conn.execute(f"ALTER TABLE {name} RENAME TO _{model}")
                conn.execute(create_stmt)
                shared_rows = [n for r in conn.execute(
                    f'select name from pragma_table_info("{name}") join pragma_table_info("_{name}") using (name)'
                    ) for n in r]
                log.warning(f"migrating table {name} while preserving fields ({', '.join(shared_rows)})")
                conn.execute(f"INSERT INTO {name} SELECT {', '.join(shared_rows)} FROM _{name}")
                conn.execute(f"DROP TABLE _{name}")
                altered = True

    if altered:
        log.info(f"cleaning {database}")
        connect().execute("VACUUM")

    log.info(f"database {database} ok")
    return connect


def clean_dict(d):
    return {k: v.id if isinstance(v, _model_row) else v for k, v in d.items()}


def _named_list(*names, **defaults):
    names = (*names, *defaults)

    class named_list:
        def __init__(self, *args, **kwargs):
            args = list(reversed(args))
            object.__setattr__(self, "_fields", {})
            try:
                for n in names:
                    setattr(self, n, kwargs.pop(n) if n in kwargs else args.pop() if args else defaults[n])
            except KeyError:
                raise TypeError(f"Not enough arguments passed to {type(self)}.")
            if args or kwargs:
                j = ', '.join
                raise TypeError(
                    f"Extra arguments passed to {type(self)} "
                    f"({j((*j(map(repr, args)), j(f'{k}={v!r}' for k, v in kwargs.items())))})."
                )

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

        def __repr__(self):
            return repr(self._fields)

    return named_list


# track registered types and provide a way to register more
# converter(bytes) -> obj  and  adapter(obj) -> int, float, str, or bytes
types = type('Type', (dict,),{
    'register': lambda ns, t, n, c, a: (ns.__setitem(t, n), sql.register_converter(n, c), sql.register_adapter(t, a)),
})({
    type(None): "NULL", int: "INTEGER", float: "REAL", str: "TEXT", bytes: "BLOB", date: "DATE", datetime: "TIMESTAMP",
})


class Field(
    _named_list(
        "type",
        default=None, primary_key=False, not_null=False, on_delete="", on_update="", generate="", stored=False, name=""
    )
):
    def __str__(self):
        return " ".join(
            value for condition, value in zip(
                (
                    self.name, self.type, self.on_delete, self.on_update, self.default,
                    self.primary_key, self.not_null, self.generate, self.stored
                ),
                (
                    self.name,
                    [types.get(self.type, "BLOB"), f'INTEGER REFERENCES {self.type}'][issubclass(self.type, Model)],
                    f'ON DELETE {self.on_delete}', f'ON UPDATE {self.on_update}',
                    # run any adapters, but not any converters. should be 'safe'
                    f"DEFAULT ({sql.connect(':memory:').execute('select ?', (self.default,)).fetchone()[0]!r})",
                    "PRIMARY KEY", "NOT NULL", f'AS {self.generate}', "STORED",
                )
            ) if condition
        )


class _model_row:
    pass


class _model_meta(type):
    def __new__(cls, name, bases, dct):
        dct.update({k: Field(**{**v._fields, "name": k}) for k, v in dct.items() if isinstance(v, Field)})
        for base in bases:
            dct.update({k: v for k, v in base.__dict__.items() if k not in dct and isinstance(v, Field)})
        dct['_fields'] = tuple((v for v in dct.values() if isinstance(v, Field)))
        model = super().__new__(cls, name, bases, dct)

        class model_row(_named_list(**{f.name: f.default for f in model}), _model_row):
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
                    with model._connect() as conn:
                        conn.execute(render, self._fields)
                    self.id = None
                    return True
                return False

            def save(self):
                render = (
                    f"INSERT INTO {model} VALUES ({', '.join(f':{f.name}' for f in model)}) "
                    f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{f.name}=:{f.name}' for f in model)} "
                    f"WHERE id=:id"
                )
                with model._connect() as conn:
                    self.id = conn.execute(render, clean_dict(self._fields)).lastrowid or self.id
                return self

            def __eq__(self, other):
                # a row is also considered equal to its id
                return isinstance(other, int) and self.id == other or super().__eq__(other)

        model_row.__name__ = model.__name__ + "_row"
        model.row = model_row
        return model

    def __str__(cls):
        return cls.__name__.lower()

    def __iter__(cls):
        return iter(cls._fields)

    def __repr__(self):
        return f"CREATE TABLE {self} ({', '.join(map(str, self))})"

    def _connect(cls):
        conn = cls._db()
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
    _special = False  # marker for sqlite reserved tables
    id = Field(int, primary_key=True, not_null=True)

    def __init__(self, *values, **filters):
        self.__values = values
        self.__filters = filters

    def __getitem__(self, item):
        if not isinstance(item, tuple):
            item = item,
        return type(self)(*self.__values, *item, **self.__filters)

    def __call__(self, **filters):
        return type(self)(*self.__values, **self.__filters, **filters)

    def __repr__(self):
        """Represent the query that would be executed minus type adaptation."""
        query, params = self._render
        for k, v in params.items():
            query = query.replace(f':{k}', repr(v))
        return query

    @property
    def _render(self):
        # render where clause
        cmp = {"eq": "=", "gt": ">", "lt": "<", "ge": ">=", "le": "<=", "ne": "<>", "in": "in"}
        clauses = []
        for filter, value in clean_dict(self.__filters).items():
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
        return (
            f"SELECT {', '.join(self.__values) or '*'} FROM {type(self)} WHERE {' AND '.join(clauses) or 1}",
            clean_dict(self.__filters),
        )

    def __iter__(self):
        with type(self)._connect() as conn:
            if self.__values:
                conn.row_factory = Row
            return conn.execute(*self._render)

    def all(self):
        return iter(self).fetchall()

    def first(self):
        return iter(self).fetchone()

    def delete(self):
        """return a count of deleted objects."""
        raise NotImplementedError

    def update(self, **fields):
        """return a count of updated objects."""
        raise NotImplementedError
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
        items = iter(self(*self.__values, **filters) if filters else self).fetchmany(2)
        if len(items) != 1: raise ValueError(f"{['No', 'Multiple'][bool(items)]} objects returned by get.")
        return items[0]

    def create(self, **filters):
        # ignore fields with lookups
        return type(self).row(**{k: v for k, v in {**self.__filters, **filters}.items() if not k.contains("__")}).save()

    def get_or_create(self, **filters):
        return self.get(**filters) or self.create(**filters)


class sqlite_master(Model):
    _special = True # sqlite_master is
    id = None  # don't include id field
    type = name = tbl_name = Field(str)
    root_page = Field(int)
    sql = Field(str)

    def create(self, **filters):
        raise TypeError("cannot update special table.")

    update = delete = create


class TestCase(unittest.TestCase):
    db = "file::memory:?cache=shared"

    def setUp(self):
        """Drop all tables before each test"""
        with sql.connect(self.db, uri=True) as conn:
            for r in conn.execute("select name from sqlite_master where type='table'").fetchall():
                conn.execute(f"drop table {r[0]}")

    def initDatabase(self):
        return initialize_database(self.db)


class LibTest(TestCase):
    @classmethod
    def setUpClass(cls):
        logging.basicConfig(level=logging.WARNING)

        class Artist(Model):
            first_name = last_name = Field(str, "NA")
            birthday = Field(date, date(1000, 1, 1), not_null=True)

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
        self.assertEqual("name TEXT", str(Field(str, name="name")))
        self.assertEqual(
            "name TEXT DEFAULT ('bruh') NOT NULL",
            str(Field(str, name="name", default='bruh', not_null=True)),
        )
        # table
        self.assertEqual(
            f"CREATE TABLE {self.artist} ("
            "first_name TEXT DEFAULT ('NA'), "
            "last_name TEXT DEFAULT ('NA'), "
            "birthday DATE DEFAULT ('1000-01-01') NOT NULL, "
            "id INTEGER PRIMARY KEY NOT NULL)",
            repr(self.artist),
        )
        connect = self.initDatabase()
        id = connect().execute(
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
            [first_name, last_name, date(year=1000, month=1, day=1), 1],
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

        bd = date(1995, 10, 21)
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
