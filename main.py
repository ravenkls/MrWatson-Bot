from database import Database


class Member:
    def __init__(self, id):
        self.id = id


hodor = Member(420961337448071178)
watson = Member(596743813385682945)

db = Database()
db.add_rep(hodor)
db.add_rep(watson)

db.cursor.execute("SELECT * FROM reputation_points;")
print(db.cursor.fetchall())
