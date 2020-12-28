from orm.orm import *
logging.basicConfig(level=logging.DEBUG)
class Artist(Model):
    first_name = last_name = F(str, not_null=True)

db = Database('test.db')
execute = db.conn.execute