import psycopg2
import os


class Database:
    """A database access object for interacting with the bot database."""

    def __init__(self):
        self.conn = psycopg2.connect(os.environ.get("DATABASE_URL"), sslmode="require")
        self.cursor = self.conn.cursor()
        self.init_tables()
    
    def init_tables(self):
        """Intialise the database tables."""
        self.cursor.execute("CREATE TABLE IF NOT EXISTS reputation_points "
                            "(member_id BIGINT PRIMARY KEY, points INTEGER);")
        self.conn.commit()
    
    def add_rep(self, member, amount=1):
        """Add X reputation points to the member."""
        self.cursor.execute("SELECT points FROM reputation_points WHERE member_id=%s;", 
                            (member.id,))

        points = self.cursor.fetchone()
        if points:
            new_points = points[0] + amount
            self.cursor.execute("UPDATE reputation_points SET points=%s WHERE member_id=%s;", 
                                (new_points, member.id))
        else:
            new_points = amount
            self.cursor.execute("INSERT INTO reputation_points (member_id, points) VALUES (%s, %s);",
                                (member.id, new_points))

        self.conn.commit()
        
        return new_points
