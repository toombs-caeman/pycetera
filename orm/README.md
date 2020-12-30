# Worst Object-Relational Mapping (WORM)


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
