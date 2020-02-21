import asyncio
import datetime
import logging
import re
import time

import discord
from discord.ext import commands, tasks

from settings import *


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


class Moderation(commands.Cog):

    BAN = "b"
    MUTE = "m"

    def __init__(self, bot):
        self.bot = bot
        self.check_expired_punishments.start()
        self.logger = logging.Logger(__name__)
        self.logger.info("Moderation cog initialised.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def adminrole(self, ctx, *, role: discord.Role=None):
        if role is None:
            role_id = ctx.bot.database.settings.get("admin_role_id")
            role = ctx.guild.get_role(int(role_id))
            if role:
                await ctx.send(f"{role} is the admin role.")
            else:
                await ctx.send("The admin role is not set.")
        else:
            self.bot.database.set_setting("admin_role_guild_id", str(ctx.guild.id))
            self.bot.database.set_setting("admin_role_id", str(role.id))
            await ctx.send(f"✅ {role.mention} is now set as the admin role.")
    
    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def modrole(self, ctx, *, role: discord.Role=None):
        if role is None:
            role_id = ctx.bot.database.settings.get("mod_role_id")
            role = ctx.guild.get_role(int(role_id))
            if role:
                await ctx.send(f"{role} is the mod role.")
            else:
                await ctx.send("The mod role is not set.")
        else:
            self.bot.database.set_setting("mod_role_guild_id", str(ctx.guild.id))
            self.bot.database.set_setting("mod_role_id", str(role.id))
            await ctx.send(f"✅ {role.mention} is now set as the mod role.")
    
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def googleit(self, ctx, member: discord.Member):
        """Run this command and chaos will ensue."""
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                              description=f"😱 {ctx.author.mention} ran the -googleit command on {member.mention}")
        await self.log(embed)
        messages = []
        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel):
                msg = await channel.send(member.mention)
                messages.append(msg)
        
        await asyncio.sleep(5)
        for m in messages:
            await m.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(is_mod)
    async def warn(self, ctx, member: discord.Member, *, reason: str="None"):
        """Warn a member of the server."""
        if ctx.author.top_role <= member.top_role:
            await ctx.send("You cannot warn this user.")
            return
        self.bot.database.add_warning(member, ctx.author, reason)
        await ctx.send(f"⚠️ {member.mention} has been warned. Reason: {reason}")
        await member.send(f"⚠️ You have been warned by {ctx.author}. Reason: {reason}")

        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                              description=f"⚠️ {member.mention} was warned by {ctx.author.mention}. Reason: {reason}")
        await self.log(embed)

    @commands.command(aliases=["warns"])
    @commands.guild_only()
    @commands.check(is_mod)
    async def warnings(self, ctx, member: discord.Member, page: int=1):
        """Retrieve all the warnings that a user has been given."""
        warnings = self.bot.database.get_warnings(member)

        pages = (len(warnings)-1) // 6 + 1
        if page > pages:
            page = pages
        elif page < 1:
            page = 1

        if warnings:
            last_warning = warnings[0]
            last_warning_time = datetime.datetime.fromtimestamp(last_warning[2]).strftime("%d %B %Y")
            embed = discord.Embed(title="List of previously given warnings",
                                  colour=0xd0021b, 
                                  description=f"{member} has `{len(warnings)}` warnings.\n"
                                              f"Their last warning was given on {last_warning_time}")
            embed.set_thumbnail(url=member.avatar_url_as(format='png', static_format='png'))
            embed.set_author(name=str(member), icon_url=member.avatar_url_as(format='png', static_format='png'))
            embed.set_footer(text=f"Page {page} of {pages}")
            for n, w in enumerate(warnings[(page-1)*6:page*6], start=(page-1)*6 + 1):
                author_id, reason, timestamp = w
                date = datetime.datetime.fromtimestamp(timestamp)
                embed.add_field(name=f"{n}. {date.strftime('%d %B %Y %H:%M')}",
                                value=f"Reason: {reason}\n"
                                      f"Given by: {ctx.guild.get_member(author_id)}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{member} has no previous warnings.")

    @commands.command(aliases=["removewarn", "warnremove"])
    @commands.guild_only()
    @commands.check(is_mod)
    async def removewarning(self, ctx, member: discord.Member, warning_id):
        """Remove a warning given the warning ID. (See user warning list for warning IDs).
        
        To remove all warnings, replace the warning ID with the word "all\""""
        warnings = self.bot.database.get_warnings(member)
        if not warning_id.isdigit():
            if warning_id == "all":
                for w in warnings:
                    timestamp = w[-1]
                    self.bot.database.remove_warning(member, timestamp)
                await ctx.send(f"✅ All warnings for {member} have been removed.")
                embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                        description=f"⚠️ {ctx.author.mention} removed all warnings from {member.mention}")
                await self.log(embed)
            else:
                raise ValueError("Warning ID must be a number.")
        else:
            warning_id = int(warning_id)
            if warning_id < 1:
                await ctx.send(f"There is no warning with the ID {warning_id}")
                return
            try:
                warning = warnings[warning_id-1]
            except IndexError:
                await ctx.send(f"There is no warning with the ID {warning_id}")
            else:
                author_id, reason, timestamp = warning
                self.bot.database.remove_warning(member, timestamp)
                await ctx.send(f"✅ The warning given to {member} by {ctx.guild.get_member(author_id)} "
                               f"for reason: \"{reason}\" has been removed.")
                           
                embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                      description=f"⚠️ {ctx.author.mention} removed a warning from {member.mention}")
                await self.log(embed)

    @commands.command(aliases=["vckick"])
    @commands.guild_only()
    @commands.check(is_mod)
    async def voicekick(self, ctx, member: discord.Member, *, reason: str="None"):
        """Kick a member from voice chat."""
        if member.voice is not None:
            if ctx.author.top_role <= member.top_role:
                await ctx.send("You cannot kick this user from voice.")
                return
            kick_channel = await ctx.guild.create_voice_channel(name=self.bot.user.name)
            await member.move_to(kick_channel)
            await kick_channel.delete()
            await ctx.send("{0.name} has been kicked from voice".format(member))
            
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🎤 {member.mention} was kicked from voice by {ctx.author.mention}")
            await self.log(embed)

        else:
            await ctx.send("{0.name} is not in a voice channel".format(member))

    @commands.command(aliases=["clear", "clean", "cls"])
    @commands.guild_only()
    @commands.check(is_admin)
    async def purge(self, ctx, limit=100, member: discord.Member=None):
        """Remove messages from a channel."""
        if member is not None:
            await ctx.channel.purge(limit=limit, check=lambda m: m.author is member)
        else:
            await ctx.channel.purge(limit=limit)
        completed = await ctx.send(":ok_hand:")

        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                              description=f"🗑️ {limit} messages have been cleared by {ctx.author.mention} in {ctx.channel.mention}")
        await self.log(embed)

        await asyncio.sleep(2)
        await completed.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def ban(self, ctx, member: discord.Member, *, reason="None", flags=None):
        """Ban a member from the server, to make the ban temporary, add the `-t` flag to the end.
        Usage examples:
        -ban Member#4209 breaking rules -t 2d
        -ban Member#4209 being stupid
        -ban Member#4209 -t 1w
        -ban Member#4209
        """

        if ctx.author.top_role <= member.top_role:
            await ctx.send("You cannot ban this user.")
            return

        reason, total_time, expiry_time = self.parse_reason_with_time_flags(reason)

        await ctx.guild.ban(member, reason=f"Banned by {ctx.author}. Reason: {reason}")
        if expiry_time >= 0:
            self.bot.database.new_punishment(member, self.BAN, expiry_time)
            await ctx.send(f"✅ {member} has been banned for {str(total_time)}. Reason: {reason}")
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🔨 {member} was banned from the server for {str(total_time)} by {ctx.author.mention}. Reason: {reason}")
        else:
            await ctx.send(f"✅ {member} has been permanently banned. Reason: {reason}")
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🔨 {member} was banned from the server permanently by {ctx.author.mention}. Reason: {reason}")
        await self.log(embed)
    
    @commands.command()
    @commands.guild_only()
    @commands.check(is_mod)
    async def mute(self, ctx, member: discord.Member, *, reason="None", flags=None):
        """Mute a member in the server, to make the mute temporary, add the `-t` flag to the end.
        Usage examples:
        -mute Member#4209 breaking rules -t 2d
        -mute Member#4209 being stupid
        -mute Member#4209 -t 1w
        -mute Member#4209
        """

        if ctx.author.top_role <= member.top_role:
            await ctx.send("You cannot mute this user.")
            return

        reason, total_time, expiry_time = self.parse_reason_with_time_flags(reason)
        mute_role_guild = self.bot.database.settings.get('guild_mute_role_id')
        if not mute_role_guild:
            await ctx.send("You haven't set a mute role yet, do this using the `-muterole` command!")
            return
        
        guild = self.bot.get_guild(int(mute_role_guild))
        role = guild.get_role(int(self.bot.database.settings.get('mute_role_id')))
        await member.add_roles(role, reason=f"Muted by {ctx.author}. Reason: {reason}")
        if expiry_time >= 0:
            self.bot.database.new_punishment(member, self.MUTE, expiry_time)
            await ctx.send(f"✅ {member} has been muted for {str(total_time)}. Reason: {reason}")
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🙊 {member} was muted in all text channels for {str(total_time)} by {ctx.author.mention}. Reason: {reason}")
        else:
            await ctx.send(f"✅ {member} has been muted indefinitely. Reason: {reason}")
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR,
                                  description=f"🙊 {member} was muted in all text channels indefinitely by {ctx.author.mention}. Reason: {reason}")
        await self.log(embed)
    
    @commands.command()
    @commands.guild_only()
    @commands.check(is_mod)
    async def unmute(self, ctx, member: discord.Member):
        """Unmute a member in the server."""

        if ctx.author.top_role <= member.top_role:
            await ctx.send("You cannot unmute this user.")
            return

        res = await self.unmute_member(member)
        if res == "No Role":
            await ctx.send("You haven't set a mute role yet, do this using the `-muterole` command!")
            return
        elif res:
            await ctx.send(f"✅ {member} has been unmuted")
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR,
                                description=f"🙊 {member} was unmuted by {ctx.author.mention}.")
            await self.log(embed)
        else:
            await ctx.send(f"{member} isn't muted.")

    async def unmute_member(self, member: discord.Member):
        mute_role_guild = self.bot.database.settings.get('guild_mute_role_id')
        if not mute_role_guild:
            return "No Role"

        guild = self.bot.get_guild(int(mute_role_guild))
        role = guild.get_role(int(self.bot.database.settings.get('mute_role_id')))
        if role in member.roles:
            await member.remove_roles(role)
            return True
        else:
            return False

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def muterole(self, ctx, role: discord.Role):
        """Set the mute role."""
        text_overwrite = discord.PermissionOverwrite(send_messages=False, add_reactions=False)
        voice_overwrite = discord.PermissionOverwrite(speak=False)

        msg = await ctx.send("🔄 Setting up permissions...")

        for channel in ctx.guild.channels:
            if isinstance(channel, discord.TextChannel):
                await channel.set_permissions(role, overwrite=text_overwrite)
            # elif isinstance(channel, discord.VoiceChannel):
            #     await channel.set_permissions(role, overwrite=voice_overwrite, reason=reason)
        
        self.bot.database.set_setting('guild_mute_role_id', str(ctx.guild.id))
        self.bot.database.set_setting('mute_role_id', str(role.id))
        await msg.edit(content=f"✅ {role.mention} is now set as the mute role.")

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def kick(self, ctx, member: discord.Member, *, reason="None"):
        """Kick a member from the server."""
        if ctx.author.top_role <= member.top_role:
            await ctx.send("You cannot ban this user.")
            return
        await ctx.guild.kick(member, reason=f"Kicked by {ctx.author}. Reason: {reason}")
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                              description=f"👢 {member} was kicked from the server by {ctx.author.mention}")
        await self.log(embed)
        await ctx.send(f"✅ {member} has been kicked from the server. Reason: {reason}")

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def roleping(self, ctx, *, role: discord.Role):
        """Pings a Role that isn't pingable by everyone."""
        previous_setting = role.mentionable
        if not role.mentionable:
            await role.edit(mentionable=True)
        await ctx.send(role.mention)
        if not previous_setting:
            await role.edit(mentionable=previous_setting)
        await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    @commands.check(is_admin)
    async def logchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel in which logs are sent."""
        self.bot.database.set_setting("log_guild_id", str(channel.guild.id))
        self.bot.database.set_setting("log_channel_id", str(channel.id))
        await ctx.send(f"✅ {channel.mention} is now the log channel.")

    @tasks.loop(minutes=1, reconnect=True)
    async def check_expired_punishments(self):
        self.logger.debug('Checking for expired punishments')
        punishments = self.bot.database.get_expired_punishments()
        if punishments:
            self.logger.debug('Punishments found!')
        for p in punishments:
            self.logger.debug(p)
            member_id, guild_id, punishment_type = p
            guild = self.bot.get_guild(guild_id)
            if punishment_type == self.BAN:
                bans = await guild.bans()
                for b in bans:
                    if b.user.id == member_id:
                        await guild.unban(b.user)
                        break
            elif punishment_type == self.MUTE:
                member = guild.get_member(member_id)
                await self.unmute_member(member)

    async def log(self, embed):
        """Log messages if the log channel is enabled."""
        guild_id = self.bot.database.settings.get('log_guild_id')
        channel_id = self.bot.database.settings.get('log_channel_id')
        if guild_id:
            guild = self.bot.get_guild(int(guild_id))
            channel = guild.get_channel(int(channel_id))
            await channel.send(embed=embed)

    def parse_reason_with_time_flags(self, reason):
        expiry_time = -1
        total_time = -1
        reason_split = reason.strip().split("-t")
        reason = reason_split[0]
        if reason.strip() == "":
            reason = "None"
        if len(reason_split) > 1:
            time_flag = reason_split[1]
            times = re.findall(r'(?:\d+w)?(?:\d+d)?(?:\d+h)?(?:\d+m)?', time_flag)

            weeks = 0
            days = 0
            hours = 0
            minutes = 0
            for t in times:
                if t.endswith('w'):
                    weeks = int(t[:-1])
                elif t.endswith('d'):
                    days = int(t[:-1])
                elif t.endswith('h'):
                    hours = int(t[:-1])
                elif t.endswith('m'):
                    minutes = int(t[:-1])
            total_time = datetime.timedelta(days=7*weeks + days, hours=hours, minutes=minutes)
            expiry_time = time.time() + total_time.total_seconds()

        return reason, total_time, expiry_time

def setup(bot):
    bot.add_cog(Moderation(bot))
