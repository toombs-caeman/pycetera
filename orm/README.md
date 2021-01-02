# Worst Object-Relational Mapping (WORM)

TODO generate feature list and status via testcases? maybe w/ git hook?
for now start with a feature list and a stop condition. I'm thinking 1000 lines (not including tsts)

# features
* manage database options
    * reasonable defaults for testing in memory
* enhanced query logging
* automated migrations

# future features
TODO
* fix up default value handling. I'm inclined to handle it entirely python side
  since sqlite3's converter/adapter handling is atrocious.
* wrap/fix up converter/adapter/TYPES handling
* try to make it thread-safe by handling connections correctly
  """

# design
Every Model subclass represents a table (unless its name begins with '_' in which case it is considered abstract).
That table's fields are determined by Field instances defined on the class.
A Model instance represents a query into that table.
Queries return a ModelRow subclass specific to that Model, also available as `Model.row`.
A ModelRow's fields are available as attributes, along with the methods `save` and `delete`.



`__repr__` is used to return strings needed to create the *sql* object, not the *python* object, as it is usually used.
`__str__` is used similarly to reference a sql object in a query. 
As such, `str(Model)` returns the table name, while `repr(Model)` returns a create table sql statement.
They are the same for a query object.
