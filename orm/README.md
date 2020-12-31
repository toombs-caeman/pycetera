# Worst Object-Relational Mapping (WORM)

TODO generate feature list and status via testcases? maybe w/ git hook?
for now start with a feature list and a stop condition. I'm thinking 1000 lines (not including tsts)

# features

# future features

# design
`__repr__` is used to return strings needed to create the *sql* object, not the *python* object, as it is usually used.
`__str__` is used similarly to reference a sql object in a query. 
As such, `str(Model)` returns the table name, while `repr(Model)` returns a create table sql statement.
They are the same for a query object.


# row
* render instance as upsert|delete
* access fields by name or index

# model
* render
  * class as create table
  * instance as select
* update and delete are separate methods  


# field
* render instance as column def

# lookups

# foreign keys
maybe features?
* reverse lookups
* select_with

# types

# database
* convert to just a single init function
  """

"works" with a sqlite backend

TODO
* fix up default value handling. I'm inclined to handle it entirely python side
  since sqlite3's converter/adapter handling is atrocious.
* wrap/fix up converter/adapter/TYPES handling
* try to make it thread-safe by handling connections correctly
  """
