from orm.orm import *
logging.basicConfig(level=logging.INFO)


class Person(Model):
    first_name = last_name = Field(str, "NA")
    birthday = Field(datetime.date, datetime.date(1000, 1, 1), not_null=True)

class Artist(Person):
    genre = Field(str)

class Album(Model):
    artist = Field(Artist, not_null=True)
    title = Field(str, not_null=True)




db = initialize_database('test.db')
run = db().execute

print(Artist(id=1)['first_name'].first())
doja = Artist.row("Doja", "Cat").save()
hot_pink = Album.row(doja, "Hot Pink").save()

bd = datetime.date(1995, 10, 21)
mushroom = Artist.row("Infected", "Mushroom", bd).save()
nasa = Album.row(mushroom, "Head of NASA and the two Amish boys").save()
shawarma = Album.row(mushroom, "The Legend of the Black Shawarma").save()
