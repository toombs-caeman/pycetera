from orm.orm import *
logging.basicConfig(level=logging.DEBUG)


class Artist(Model):
    first_name = last_name = Field(str, "NA")
    birthday = Field(datetime.date, datetime.date(1000, 1, 1), not_null=True)


class Album(Model):
    artist = Field(Artist, not_null=True)
    title = Field(str, not_null=True)


db = Database('test.db')
run = db.conn.execute

doja = Artist.row("Doja", "Cat").save()
hot_pink = Album.row(doja, "Hot Pink").save()

bd = datetime.date(1995, 10, 21)
mushroom = Artist.row("Infected", "Mushroom", bd).save()
nasa = Album.row(mushroom, "Head of NASA and the two Amish boys").save()
shawarma = Album.row(mushroom, "The Legend of the Black Shawarma").save()
