import discord
from settings import *
from discord.ext import commands
import logging


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class AssignRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("AssignRoles cog initialised.")
    
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def addrolereaction(self, ctx, message_id: int, emoji, role: discord.Role):
        message = await ctx.channel.fetch_message(message_id)
        self.bot.database.add_role_reaction(message.id, emoji, role)
        await message.add_reaction(emoji)
    
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def removerolereaction(self, ctx, message_id, emoji):
        message = await ctx.channel.fetch_message(message_id)
        self.bot.database.delete_role_reaction(message.id, emoji)
        await message.remove_reaction(emoji, ctx.guild.get_member(self.bot.user.id))
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        role_id = self.bot.database.check_reaction(payload.message_id, payload.emoji)
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            await payload.member.add_roles(role)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        role_id = self.bot.database.check_reaction(payload.message_id, payload.emoji)
        if role_id:
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            await payload.member.remove_roles(role)

def setup(bot):
    bot.add_cog(AssignRoles(bot))
