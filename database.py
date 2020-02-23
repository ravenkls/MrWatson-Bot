import asyncio
import asyncpg
from settings import DATABASE_URL
import time
import os


class Database:
    """A database access object for interacting with the bot database."""

    def __init__(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.connect_to_database())
    
    async def connect_to_database(self):
        self.conn = await asyncpg.connect(DATABASE_URL + "?sslmode=require")
        self.settings = await self.load_settings()
        await self.init_tables()
    
    async def init_tables(self):
        """Intialise the database tables."""
        await self.conn.execute("CREATE TABLE IF NOT EXISTS reputation_points "
                                "(member_id BIGINT PRIMARY KEY, points INTEGER);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS warnings "
                                "(member_id BIGINT, author BIGINT, reason TEXT, timestamp BIGINT);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS temporary_punishments "
                                "(member_id BIGINT, guild_id BIGINT, type CHAR(1), expiry_date BIGINT);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS helper_roles (guild_id BIGINT, channel_id BIGINT, role_id BIGINT);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS assign_role_reactions "
                                "(message_id BIGINT, emoji TEXT, role_id BIGINT, nick_addition TEXT);")
        await self.conn.execute("CREATE TABLE IF NOT EXISTS demographic_roles "
                                "(role_id BIGINT PRIMARY KEY);")
    
    async def load_settings(self):
        """Load settings from database."""
        results = await self.conn.fetch("SELECT * FROM settings;")
        return {r["key"]: r["value"] for r in results}
    
    async def set_setting(self, key, value):
        """Set a setting value."""
        if key in self.settings:
            await self.conn.execute("UPDATE settings SET value=$1 WHERE key=$1;", value, key)
        else:
            await self.conn.execute("INSERT INTO settings (key, value) VALUES ($1, $2);", key, value)
        self.settings[key] = value

    async def add_demographic_role(self, role):
        await self.conn.execute("INSERT INTO demographic_roles (role_id) VALUES ($1);", role.id)
    
    async def remove_demographic_role(self, role):
        await self.conn.execute("DELETE FROM demographic_roles WHERE role_id=$1", role.id)

    async def get_demographic_roles(self):
        result = await self.conn.fetch("SELECT role_id FROM demographic_roles;")
        if result:
            return [r["role_id"] for r in result]

    async def add_helper_role(self, channel, role):
        """Add a helper role for a channel."""
        if role.id in self.get_helper_roles(channel):
            return
        await self.conn.execute("INSERT INTO helper_roles (guild_id, channel_id, role_id) VALUES ($1, $2, $3);",
                                channel.guild.id, channel.id, role.id)

    async def get_helper_roles(self, channel):
        """Get the helper role for a channel."""
        results = await self.conn.fetch("SELECT role_id FROM helper_roles WHERE guild_id=$1 AND channel_id=$2",
                                        channel.guild.id, channel.id)
        return [r["role_id"] for r in results]
    
    async def add_role_reaction(self, message_id, emoji, role, nick):
        """Add a role reaction."""
        await self.conn.execute("INSERT INTO assign_role_reactions (message_id, emoji, role_id, nick_addition) "
                                "VALUES ($1, $2, $3, $4);", message_id, str(emoji), role.id, nick)

    async def remove_role_reaction(self, message_id, emoji):
        """Remove a role reaction."""
        await self.conn.execute("DELETE FROM assign_role_reactions WHERE message_id=$1 AND emoji=$2;",
                                message_id, str(emoji))
    
    async def check_reaction(self, message_id, emoji):
        """Check roles for a reaction to a message."""
        result = await self.conn.fetchrow("SELECT role_id, nick_addition FROM assign_role_reactions WHERE message_id=$1 AND emoji=$2;",
                                          message_id, str(emoji))
        return result["role_id"], result["nick_addition"]

    async def remove_helper_role(self, channel, role_id):
        """Remove a helper role from a channel."""
        await self.conn.execute("DELETE FROM helper_roles WHERE guild_id=$1 AND channel_id=$2 AND role_id=$3;",
                                channel.guild.id, channel.id, role_id)

    async def new_punishment(self, member, punishment_type, expire_date):
        """Add temporary punishment to the database."""
        await self.conn.execute("INSERT INTO temporary_punishments (member_id, guild_id, type, expiry_date) "
                                "VALUES ($1, $2, $3, $4);", member.id, member.guild.id, punishment_type, expire_date)

    async def get_expired_punishments(self):
        """Retrieve any expired punishments."""
        time_now = time.time()
        expired = await self.conn.fetch("SELECT member_id, guild_id, type FROM temporary_punishments WHERE expiry_date < $1;", time_now)
        if expired:
            await self.conn.execute("DELETE FROM temporary_punishments WHERE expiry_date < $1;", time_now)
        return [(e["member_id"], e["guild_id"], e["type"]) for e in expired]
    
    async def get_temporary_punishments(self):
        """Get all active punishments"""
        result = await self.conn.fetch("SELECT member_id, type, expiry_date FROM temporary_punishments ORDER BY expiry_date;")
        return [(r["member_id"], r["type"], r["expiry_date"]) for r in result]

    async def add_warning(self, member, author, reason):
        """Add a warning to a member."""
        t = time.time()*100
        await self.conn.execute("INSERT INTO warnings (member_id, author, reason, timestamp) "
                                "VALUES ($1, $2, $3, $4);", member.id, author.id, reason, t)
    
    async def remove_warning(self, member, timestamp):
        """Remove a warning from a member."""
        await self.conn.execute("DELETE FROM warnings WHERE member_id=$1 AND timestamp=$2;", 
                                  member.id, timestamp*100)
    
    async def get_warnings(self, member):
        """Retrieve all warnings given to a user."""
        results = await self.conn.fetch("SELECT author, reason, timestamp FROM warnings WHERE member_id=$1 ORDER BY timestamp DESC;", 
                                        member.id)
        
        warnings = []
        for result in results:
            warnings.append((result["author"], result["reason"], result["timestamp"]/100))

        return warnings

    async def add_rep(self, member, amount=1):
        """Add X reputation points to the member."""
        points = await self.get_reps(member)

        if points:
            new_points = points + amount
            result = await self.set_reps(member, new_points)
        else:
            new_points = amount
            result = await self.set_reps(member, new_points)

        return result
    
    async def set_reps(self, member, amount):
        """Set the reps for a member to a specific value."""
        points = await self.get_reps(member)
        if amount > 100000000:
            amount = 100000000
        if amount < 0:
            amount = 0
        if points:
            if amount != 0:
                await self.conn.execute("UPDATE reputation_points SET points=$1 WHERE member_id=$2;", 
                                        amount, member.id)
            else:
                await self.conn.execute("DELETE FROM reputation_points WHERE member_id=$1", member.id)
        elif amount != 0:
            await self.conn.execute("INSERT INTO reputation_points (member_id, points) VALUES ($1, $2);",
                                    member.id, amount)

        return amount

    async def get_reps(self, member):
        """Retrieve the reputation points for a member."""
        reps = await self.conn.fetchrow("SELECT points FROM reputation_points WHERE member_id=$1;", 
                                        member.id)
        if reps:
            return reps["points"]
        else:
            return 0
    
    async def get_top_reps(self, amount=10):
        """Retrieve the top X people by reps."""
        results = await self.conn.fetch("SELECT * FROM reputation_points ORDER BY points DESC LIMIT $1;",
                                        amount)
        return [(r["member_id"], r["points"]) for r in results]
    
    async def clear_reputations(self):
        """Remove all reputations from the table."""
        await self.conn.execute("DELETE FROM reputation_points;")
