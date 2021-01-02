from orm.orm import *
logging.basicConfig(level=logging.DEBUG)


class Person(Model):
    first_name = last_name = Field(str, "NA")
    birthday = Field(sql.Date, sql.Date(1000, 1, 1), not_null=True)

class Artist(Person):
    genre = Field(str)

class Album(Model):
    artist = Field(Artist, not_null=True)
    title = Field(str, not_null=True)
    rating = Field(int)


print(repr(Album))



db = initialize_database('test.db', debug=True, allow_migrations=True)
run = db().execute

doja = Artist.get_or_create(first_name="Doja", last_name="Cat")
if not Album(artist=doja):
    hot_pink = Album.row(doja, "Hot Pink").save()

bd = sql.Date(1995, 10, 21)
mushroom = Artist.row("Infected", "Mushroom", bd).save()
nasa = Album.row(mushroom, "Head of NASA and the two Amish boys").save()
shawarma = Album.row(mushroom, "The Legend of the Black Shawarma").save()
