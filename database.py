import psycopg2
from settings import DATABASE_URL
import os


class Database:
    """A database access object for interacting with the bot database."""

    def __init__(self):
        self.conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        self.cursor = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        """Intialise the database tables."""
        self.cursor.execute("CREATE TABLE IF NOT EXISTS reputation_points "
                            "(member_id BIGINT PRIMARY KEY, points INTEGER);")
        self.conn.commit()
    
    def add_rep(self, member, amount=1):
        """Add X reputation points to the member."""
        points = self.get_reps(member)

        if points:
            new_points = points + amount
            if new_points > 100000000:
                new_points = 100000000
            self.set_reps(member, new_points)
        else:
            new_points = amount
            if new_points > 100000000:
                new_points = 100000000
            self.set_reps(member, new_points)
        self.conn.commit()

        return new_points
    
    def set_reps(self, member, amount):
        """Set the reps for a member to a specific value."""
        points = self.get_reps(member)
        if amount > 100000000:
            amount = 100000000
        if points:
            if amount != 0:
                self.cursor.execute("UPDATE reputation_points SET points=%s WHERE member_id=%s;", 
                                    (amount, member.id))
            else:
                self.cursor.execute("DELETE FROM reputation_points WHERE member_id=%s", (member.id))
        elif amount != 0:
            self.cursor.execute("INSERT INTO reputation_points (member_id, points) VALUES (%s, %s);",
                                (member.id, amount))
        self.conn.commit()

        return amount

    def get_reps(self, member):
        """Retrieve the reputation points for a member."""
        self.cursor.execute("SELECT points FROM reputation_points WHERE member_id=%s;", 
                            (member.id,))
        points = self.cursor.fetchone()
        if points:
            return points[0]
        else:
            return 0
    
    def get_top_reps(self, amount=10):
        """Retrieve the top X people by reps."""
        self.cursor.execute("SELECT * FROM reputation_points ORDER BY points DESC LIMIT %s;",
                            (amount,))
        return self.cursor.fetchall()
    
    def clear_reputations(self):
        """Remove all reputations from the table."""
        self.cursor.execute("DELETE FROM reputation_points;")
        self.conn.commit()