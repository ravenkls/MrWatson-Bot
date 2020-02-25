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


async def is_mod(ctx):
    role_id = ctx.bot.database.settings.get("mod_role_id")
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
    async def addrolereaction(self, ctx, message_id: int, emoji, role: discord.Role, *, nick=None):
        message = await ctx.channel.fetch_message(message_id)
        await self.bot.database.add_role_reaction(message.id, emoji, role, nick)
        await message.add_reaction(emoji)
    
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def removerolereaction(self, ctx, message_id, emoji):
        message = await ctx.channel.fetch_message(message_id)
        await self.bot.database.remove_role_reaction(message.id, emoji)
        await message.remove_reaction(emoji, ctx.guild.get_member(self.bot.user.id))

    @commands.command(aliases=["nick"])
    @commands.guild_only()
    @commands.check(is_mod)
    async def nickname(self, ctx, member: discord.Member, *, nickname=None):
        """Change someones nickname, to remove your nickname just type `-nickname` on its own."""
        if nickname is None:
            year = member.nick.split("||")[-1].strip()
            if member.name + " || " + year == member.nick:
                await ctx.send(f"{member} already has no nickname! To assign a nickname type `-nickname <nickname>`")
            else:
                await member.edit(nick=member.name + " || " + year)
                await ctx.send(f"{member}'s nickname has been reset.")
        else:
            year = member.nick.split("||")[-1].strip()
            await member.edit(nick=nickname + " || " + year)
            await ctx.send(f"{member}'s nickname has been set!")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        check = await self.bot.database.check_reaction(payload.message_id, payload.emoji)
        if check:
            role_id, nick = check
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            if not payload.member.bot:
                try:
                    await payload.member.add_roles(role)
                except discord.errors.Forbidden:
                    self.logger.warning("Permission denied when adding roles.")
                
                if nick:
                    try:
                        await payload.member.edit(nick=payload.member.name + " || " + nick)
                    except discord.errors.Forbidden:
                        self.logger.warning("Permission denied when setting nickname.")
                
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        check = await self.bot.database.check_reaction(payload.message_id, payload.emoji)
        if check:
            role_id, nick = check
            guild = self.bot.get_guild(payload.guild_id)
            role = guild.get_role(role_id)
            member = guild.get_member(payload.user_id)
            if not member.bot:
                try:
                    await member.remove_roles(role)
                except discord.errors.Forbidden:
                    self.logger.warning("Permission denied when removing role.")
            
                if nick:
                    try:
                        await member.edit(nick=None)
                    except discord.errors.Forbidden:
                        self.logger.warning("Permission denied when setting nickname.")

def setup(bot):
    bot.add_cog(AssignRoles(bot))
