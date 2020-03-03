import discord
from discord.ext import commands
import logging

from settings import *
import asyncio

async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_expired_punishments.start()
        self.logger = logging.Logger(__name__)
        self.logger.info("Events cog initialised.")

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def joinrole(self, ctx, join_role: discord.Role):
        """Setup the join role."""
        current_roles = await self.bot.database.get_join_roles()
        if join_role.id in current_roles:
            await self.bot.database.remove_join_role(join_role)
            await ctx.send(f"{join_role.mention} is no longer a join role!")
        else:
            await self.bot.database.add_join_role(join_role)
            await ctx.send(f"{join_role.mention} is now a join role!")

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin):
    async def welcomemessage(self, ctx, message: str=None, channel: discord.TextChannel=None):
        """View or set the welcome message."""
        if message is not None:
            if channel is not None:
                await self.bot.database.set_setting("welcome_message", message)
                await self.bot.database.set_setting("welcome_channel", str(channel.id))
            else:
                await ctx.send("Please specify the channel to send the welcome message!")
        else:
            message = self.bot.database.settings.get("welcome_message")
            await ctx.send(message)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        join_role_ids = await self.bot.database.get_join_roles()
        join_roles = [member.guild.get_role(jr) for jr in join_role_ids]
        await member.add_roles(*join_roles)

        await asyncio.sleep(0.5)

        format_names = {"server", member.guild.name,
                        "member", member.mention,
                        "member_count", len(member.guild.members)}

        welcome_message = self.bot.database.settings.get("welcome_message")
        welcome_channel = self.bot.database.settings.get("welcome_channel")
        if welcome_message and welcome_channel:
            channel = member.guild.get_channel(int(welcome_channel))
            await channel.send(welcome_message.format(**format_names))

            
def setup(bot):
    bot.add_cog(Events(bot))
