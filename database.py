import psycopg2
from settings import DATABASE_URL
import time
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
        self.cursor.execute("CREATE TABLE IF NOT EXISTS warnings "
                            "(member_id BIGINT, author BIGINT, reason TEXT, timestamp BIGINT);")
        self.conn.commit()
    
    def add_warning(self, member, author, reason):
        """Add a warning to a member."""
        self.cursor.execute("INSERT INTO warnings (member_id, author, reason, timestamp) "
                            "VALUES (%s, %s, %s, %s);", (member.id, author.id, reason, time.time()*100))
        self.conn.commit()
    
    def remove_warning(self, member, timestamp):
        """Remove a warning from a member."""
        self.cursor.execute("DELETE FROM warnings WHERE member_id=%s AND timestamp=%s;", 
                            (member.id, timestamp*100))
        self.conn.commit()
    
    def get_warnings(self, member):
        """Retrieve all warnings given to a user."""
        self.cursor.execute("SELECT author_id, reason, timestamp FROM warnings WHERE member_id=%s;", (member.id))
        
        warnings = []
        for result in self.cursor.fetchall():
            author_id, reason, timestamp = result
            timestamp /= 100
            warnings.append((author_id, reason, timestamp))

        return warnings

    def add_rep(self, member, amount=1):
        """Add X reputation points to the member."""
        points = self.get_reps(member)

        if points:
            new_points = points + amount
            result = self.set_reps(member, new_points)
        else:
            new_points = amount
            result = self.set_reps(member, new_points)
        self.conn.commit()

        return result
    
    def set_reps(self, member, amount):
        """Set the reps for a member to a specific value."""
        points = self.get_reps(member)
        if amount > 100000000:
            amount = 100000000
        if amount < 0:
            amount = 0
        if points:
            if amount != 0:
                self.cursor.execute("UPDATE reputation_points SET points=%s WHERE member_id=%s;", 
                                    (amount, member.id))
            else:
                self.cursor.execute("DELETE FROM reputation_points WHERE member_id=%s", (member.id,))
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