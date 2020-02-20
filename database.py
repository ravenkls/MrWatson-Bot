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
        self.settings = self.load_settings()
    
    def init_tables(self):
        """Intialise the database tables."""
        self.cursor.execute("CREATE TABLE IF NOT EXISTS reputation_points "
                            "(member_id BIGINT PRIMARY KEY, points INTEGER);")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS warnings "
                            "(member_id BIGINT, author BIGINT, reason TEXT, timestamp BIGINT);")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS temporary_punishments "
                            "(member_id BIGINT, guild_id BIGINT, type CHAR(1), expiry_date BIGINT);")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS helper_roles (guild_id BIGINT, channel_id BIGINT, role_id BIGINT);")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS assign_role_reactions "
                            "(message_id BIGINT, emoji TEXT, role_id BIGINT, nick_addition TEXT);")
        self.conn.commit()
    
    def load_settings(self):
        """Load settings from database."""
        self.cursor.execute("SELECT * FROM settings;")
        return dict(self.cursor.fetchall())
    
    def set_setting(self, key, value):
        """Set a setting value."""
        if key in self.settings:
            self.cursor.execute("UPDATE settings SET value=%s WHERE key=%s;", (value, key))
        else:
            self.cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s);", (key, value))
        self.conn.commit()
        self.settings[key] = value

    def add_helper_role(self, channel, role):
        """Add a helper role for a channel."""
        if role.id in self.get_helper_roles(channel):
            return
        self.cursor.execute("INSERT INTO helper_roles (guild_id, channel_id, role_id) VALUES (%s, %s, %s);",
                            (channel.guild.id, channel.id, role.id))
        self.conn.commit()

    def get_helper_roles(self, channel):
        """Get the helper role for a channel."""
        self.cursor.execute("SELECT role_id FROM helper_roles WHERE guild_id=%s AND channel_id=%s",
                            (channel.guild.id, channel.id))
        results = self.cursor.fetchall()
        return [r[0] for r in results]
    
    def add_role_reaction(self, message_id, emoji, role, nick):
        """Add a role reaction."""
        self.cursor.execute("INSERT INTO assign_role_reactions (message_id, emoji, role_id, nick_addition) "
                            "VALUES (%s, %s, %s, %s);", (message_id, str(emoji), role.id, nick))
        self.conn.commit()

    def remove_role_reaction(self, message_id, emoji):
        """Remove a role reaction."""
        self.cursor.execute("DELETE FROM assign_role_reactions WHERE message_id=%s AND emoji=%s;",
                            (message_id, str(emoji)))
        self.conn.commit()
    
    def check_reaction(self, message_id, emoji):
        """Check roles for a reaction to a message."""
        self.cursor.execute("SELECT role_id, nick_addition FROM assign_role_reactions WHERE message_id=%s AND emoji=%s;",
                            (message_id, str(emoji)))
        results = self.cursor.fetchone()
        return results

    def remove_helper_role(self, channel, role_id):
        """Remove a helper role from a channel."""
        self.cursor.execute("DELETE FROM helper_roles WHERE guild_id=%s AND channel_id=%s AND role_id=%s;",
                            (channel.guild.id, channel.id, role_id))
        self.conn.commit()

    def new_punishment(self, member, punishment_type, expire_date):
        """Add temporary punishment to the database."""
        self.cursor.execute("INSERT INTO temporary_punishments (member_id, guild_id, type, expiry_date) "
                            "VALUES (%s, %s, %s, %s);", (member.id, member.guild.id, punishment_type, expire_date))
        self.conn.commit()

    def get_expired_punishments(self):
        """Retrieve any expired punishments."""
        time_now = time.time()
        self.cursor.execute("SELECT member_id, guild_id, type FROM temporary_punishments WHERE expiry_date < %s;", (time_now,))
        expired = self.cursor.fetchall()
        if expired:
            self.cursor.execute("DELETE FROM temporary_punishments WHERE expiry_date < %s;", (time_now,))
            self.conn.commit()
        return expired

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
        self.cursor.execute("SELECT author, reason, timestamp FROM warnings WHERE member_id=%s;", (member.id,))
        
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