import abc
import logging
import unittest
import sqlite3 as sql

assert sql.sqlite_version_info >= (3, 24)

# TODO add color logging
# supports_color = hasattr(sys.stderr, 'isatty') and sys.stderr.isatty()
# TODO typing
log = logging.getLogger(__name__)

# Foreign key flags
Restrict = "restrict"
SetNull = "set null"
SetDefault = "set default"
Cascade = "cascade"


class Connection(sql.Connection):
    class Cursor(sql.Cursor):
        def logexec(self, f, args):
            try:
                return f(*args)
            except Exception as e:
                # TODO parse the exception and provide more detail in the re-raise
                #   sql.IntefaceError should show the problematic parameter
                #   sql.OperationalError should show the squirrelly query
                query, *params = args
                log.error(f"failed to execute query {query!r}{f'with parameters {params[0]!r}' if params else ''}")
                raise e

    for f in ('execute', 'executemany', 'executescript'):
        setattr(Cursor, f, (lambda f: lambda s, *a: s.logexec(getattr(super(type(s), s), f), a))(f))

    def cursor(self, factory=Cursor):
        return super().cursor(factory)


def initialize_database(database="file::memory:?cache=shared", debug=False, allow_migrations=False, **options):
    options = {"database": database, "detect_types": sql.PARSE_DECLTYPES, "uri": True, "factory": Connection, **options}

    keep_alive = sql.connect(**options) if 'memory' in database else None

    def connect(model=None):
        keep_alive  # keep memory-only databases alive
        c = sql.connect(**options)
        c.execute("PRAGMA FOREIGN_KEY=1")
        c.row_factory = model and (lambda c, r: model.row(*r)) or Row
        if debug:
            c.set_trace_callback(log.debug)
        return c

    # allow connections
    Model._connect = connect

    def all_subclasses(cls):
        subs = {*cls.__subclasses__()}
        return subs.union({c for s in subs for c in all_subclasses(s)})

    with connect() as conn:
        # register models
        all_models = {}
        duplicates = {}
        for model in all_subclasses(Model):
            name = str(model)
            # models that start with '_' are considered abstract
            # pseudo-models don't have an id
            if name.startswith('_') or model.id is None:
                continue
            if name in all_models:
                duplicates.setdefault(name, []).append(model.__module__)
            all_models[name] = model
        if duplicates:
            raise ImportError(
                "Duplicate model found:\n" + "\n".join(f'{name:>16} in {info}' for name, info in duplicates.items())
            )

        # migrate database
        extant_tables = dict(sqlite_master(type='table')["name", "sql"].all())
        migrations = {}
        for name, model in all_models.items():
            create_stmt = repr(model)
            if name not in extant_tables:
                conn.execute(create_stmt)  # tables can be created from scratch w/o being considered a migration
            elif create_stmt == extant_tables[name]:
                log.debug(f"table {name} ok")
            else:
                old = set(field.name for field in table_info(table=name))
                new = set(map(str, model._fields))
                shared = old.intersection(new)
                j = ', '.join
                migrations[name] = f'+({j(new - old)}) -({j(old - new)})'
                if not allow_migrations:
                    continue
                fields = j(shared)
                conn.executescript(f"""
BEGIN;
PRAGMA FOREIGN_KEY = 0;
DROP TABLE IF EXISTS _{name};
ALTER TABLE {name} RENAME TO _{name};
{create_stmt};
INSERT INTO {name}({fields}) SELECT {fields} FROM _{name};
DROP TABLE _{name};
PRAGMA FOREIGN_KEY = 1;
COMMIT;
""")

    if migrations:
        msg = '\n'.join(f'{name:>16}: {info}' for name, info in migrations.items())
        if not allow_migrations:
            raise EnvironmentError('Migrations needed, but not allowed:\n' + msg)
        else:
            log.info('Migrations performed:\n' + msg)
    else:
        log.debug(f"database {database} ok")
    return connect


def clean_dict(d):
    """Return an object suitable for saving."""
    # TODO raise error if d contains unsaved ModelRows
    return {k: v['id'] if isinstance(v, ModelRow) else v for k, v in d.items()}


# track registered types and provide a way to register more
# converter(bytes) -> obj  and  adapter(obj) -> int, float, str, or bytes
types = type('Type', (dict,), {
    'register': lambda ns, t, n, c, a: (
        ns.__setitem(t, n), sql.register_converter(n, c), sql.register_adapter(t, a)), })({
    type(None): "NULL", int: "INTEGER", float: "REAL", str: "TEXT", bytes: "BLOB", sql.Date: "DATE",
    sql.Timestamp: "TIMESTAMP",
})


class Field:
    def __init__(
            self, type, default=None, primary_key=False, not_null=False, on_delete="", on_update="", generate="",
            stored=False, name=""
    ):
        self.__dict__.update(
            name=name, type=type, on_delete=on_delete, on_update=on_update, default=default,
            primary_key=primary_key, not_null=not_null, generate=generate, stored=stored,
        )

    def __str__(self):
        return self.name

    def __repr__(self):
        return " ".join(
            value for condition, value in zip(
                self.__dict__.values(),
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


class Row(sql.Row, abc.ABC):
    def __getattr__(self, item):
        return self[item]

    def __repr__(self):
        return repr((*self,))


class ModelRow(dict):
    _model = None

    def __init__(self, *args, **kwargs):
        args = list(reversed(args))
        super().__init__(
            {
                field.name: kwargs.pop(field.name) if field.name in kwargs
                else args.pop() if args
                else field.default
                for field in self._model
            },
        )
    def __iter__(self):
        return iter(self.values())

    def __getattr__(self, item):
        value = self[item]
        # handle foreign keys
        fk = getattr(self._model, item)
        if isinstance(value, int) and issubclass(fk.type, Model):
            value = fk.type.get(id=value)
            self[item] = value
        return value

    def __setattr__(self, key, value):
        if key in self:
            self[key] = value

    def __eq__(self, other):
        # a row is also considered equal to its id
        return isinstance(other, int) and self.id == other or super().__eq__(other)

    def delete(self):
        if self.id:
            render = f'DELETE FROM {self._model} WHERE id = :id'
            with self._model._connect() as conn:
                conn.execute(render, clean_dict(self))
            self.id = None
            return True
        return False

    def save(self):
        render = (
            f"INSERT INTO {self._model} VALUES ({', '.join(f':{f}' for f in self._model)}) "
            f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{f}=:{f}' for f in self._model)} WHERE id=:id"
        )
        with self._model._connect() as conn:
            self.id = conn.execute(render, clean_dict(self)).lastrowid or self.id
        return self


Row.register(ModelRow)


class _model_meta(type):
    def __new__(cls, name, bases, dct):
        # register fields
        dct.update({k: Field(**{**v.__dict__, 'name': k}) for k, v in dct.items() if isinstance(v, Field)})
        for base in bases:
            dct.update({k: v for k, v in base.__dict__.items() if k not in dct and isinstance(v, Field)})
        # dct['_fields'] = tuple(k for k in dct if isinstance(dct[k], Field))
        dct['_fields'] = tuple((v for v in dct.values() if isinstance(v, Field)))
        # create type
        model = super().__new__(cls, name, bases, dct)
        model.row = type(f'{model}_row', (model.row,), {'_model': model})
        return model

    def __str__(cls):
        return cls.__name__.lower()

    def __iter__(cls):
        return iter(cls._fields)

    def __repr__(cls):
        return f"CREATE TABLE {cls} ({', '.join(map(repr, cls))})"


class Model(metaclass=_model_meta):
    id = Field(int, primary_key=True, not_null=True)
    row = ModelRow
    _connect = lambda s: None  # placeholder

    def __init__(self, *fields, **filters):
        self._fields = fields
        self._filters = filters

    def __getitem__(self, item):
        if not isinstance(item, tuple):
            item = item,
        return type(self)(*self._fields, *item, **self._filters)

    def __call__(self, **filters):
        return type(self)(*self._fields, **self._filters, **filters)

    def __repr__(self):
        query = self._select
        params = dict(zip(
            self._filters,
            self._connect().execute(
                f"SELECT {', '.join('?' * len(self._filters))}",
                tuple(clean_dict(self._filters).values()),
            ).fetchone(),
        ))
        for k, v in sorted(params.items(), reverse=True):  # replace longest keys first
            query = query.replace(f':{k}', v)
        return query

    def _execute(self, query):
        with type(self)._connect() if self._fields else self._connect() as conn:
            return conn.execute(query, clean_dict(self._filters))

    def __iter__(self):
        return self._execute(self._select)

    def count(self):
        return self._connect().execute(
            f"SELECT COUNT(*) FROM {type(self)} WHERE {self._where}", clean_dict(self._filters)
        ).fetchone()[0]

    @property
    def _where(self):
        cmp = {"eq": "=", "gt": ">", "lt": "<", "ge": ">=", "le": "<=", "ne": "<>", "in": "in"}
        clauses = []
        for filter, value in clean_dict(self._filters).items():
            clause = "{}"
            model = type(self)
            fields = filter.split("__")
            op = cmp[fields.pop()] if fields[-1] in cmp else "="
            for field in fields[:-1]:
                model = getattr(model, field).type
                clause = clause.format("{} IN (SELECT id FROM {} WHERE {})").format(field, model, "{}")
            clauses.append(clause.format(f'{fields[-1]} {op} :{filter}'))
        return ' AND '.join(clauses) or 1

    @property
    def _select(self):
        return f"SELECT {', '.join(map(str, type(self))) or '*'} FROM {type(self)} WHERE {self._where}"

    def all(self):
        return list(self)

    def first(self):
        return next(iter(self))

    def get(self, **filters):
        if filters: self = self(**filters)
        items = iter(self).fetchmany(2)
        if len(items) != 1: raise ValueError(f"{['No', 'Multiple'][bool(items)]} objects returned by get.")
        return items[0]

    def delete(self, **filters):
        if filters: self = self(**filters)
        return self._execute(f"DELETE FROM {type(self)} WHERE {self._where}")

    def update(self, **filters):
        if filters: self = self(**filters)
        fields = ', '.join(f'{f}=:{f}' for f in self._filters if '__' not in f)
        return self._execute(f"UPDATE {type(self)} SET {fields} WHERE {self._where}")

    def create(self, **filters):
        # ignore fields with lookups
        return type(self).row(**{k: v for k, v in {**self._filters, **filters}.items() if "__" not in k}).save()

    def get_or_create(self, **filters):
        if filters: self = self(**filters)
        try:
            return self.get()
        except ValueError:
            return self.create()


# re-expose query functions on model
for k, v in Model.__dict__.items():
    if isinstance(v, type(lambda: None)) and not k.startswith("_"):
        setattr(_model_meta, k, (lambda k: (property(lambda cls: getattr(cls(), k))))(k))


class sqlite_master(Model):
    id = None  # don't include id field
    type = name = tbl_name = Field(str)
    rootpage = Field(int)
    sql = Field(str)


class table_info(Model):
    id = None  # don't include id field
    cid = Field(int)
    name = type = Field(str)
    notnull = Field(int)
    dflt_value = Field(bytes)
    pk = Field(int)

    @property
    def _select(self):
        return f"SELECT {', '.join(self._fields) or '*'} FROM pragma_table_info('{self._filters['table']}')"


class TestCase(unittest.TestCase):
    db = "file::memory:?cache=shared"

    def setUp(self):
        """Drop all tables before each test"""
        with sql.connect(self.db, uri=True) as conn:
            for r in conn.execute("select name from sqlite_master where type='table'").fetchall():
                conn.execute(f"drop table {r[0]}")

    def initDatabase(self):
        return initialize_database(self.db, debug=True)


class LibTest(TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        logging.basicConfig(level=logging.INFO)

        class Artist(Model):
            first_name = last_name = Field(str, "NA")
            birthday = Field(sql.Date, sql.Date(1000, 1, 1), not_null=True)

        class Album(Model):
            artist = Field(Artist, not_null=True)
            title = Field(str, not_null=True)

        cls.artist = Artist
        cls.album = Album

    def test_render(self):
        # field
        self.assertEqual("S", str(Field(str, name="S")))
        self.assertEqual("name TEXT DEFAULT (3) NOT NULL", repr(Field(str, name="name", default=3, not_null=True)))
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
        omaewa = connect().execute(
            "insert into artist(last_name) values ('Ni')"
        ).execute(
            "select * from artist where last_name ='Ni'"
        ).fetchone()
        self.assertEqual(
            "NA",
            omaewa.first_name,
            msg="moushindeiru"
        )

    def test_select(self):
        first_name = "Mario"
        last_name = "Peach"
        self.initDatabase()
        self.artist.row(first_name, last_name).save()
        self.assertEqual(
            list(self.artist.get(id=1)),
            [first_name, last_name, sql.Date(year=1000, month=1, day=1), 1],
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

        bd = sql.Date(1995, 10, 21)
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
        # TODO test get_or_create default handling

    @unittest.skip(NotImplemented)
    def test_dirty_check(self):
        # track if the row is dirty, and do a recursive save over foreign keys
        pass

    @unittest.skip(NotImplemented)
    def test_slice(self):
        """
        slicing a query:
        * int -> offset n
        * slice -> limit stop - start offset start (disallow step)
        """
        pass

    @unittest.skip(NotImplemented)
    def test_migrations(self):
        """
        show that migrations:
        * only run when allow_migrations=True
        * preserve as much data as they can
        * fail and roll back on foreign key constraint failure
        """


if __name__ == '__main__':
    unittest.main()
