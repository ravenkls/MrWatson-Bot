import inspect
import asyncio
import datetime
import re
import time

import discord
from discord.ext import commands, tasks

from settings import *


class General(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command("help")
    
    def get_usage(self, command):
        """Get the usage details of a command."""
        args_spec = inspect.getfullargspec(command.callback)  # Get arguments of command
        args_info = []
        [args_info.append("".join(["<", arg, ">"])) for arg in args_spec.args[2:]]  # List arguments
        if args_spec.defaults is not None:
            for index, default in enumerate(args_spec.defaults):  # Modify <> to [] for optional arguments
                default_arg = list(args_info[-(index + 1)])
                default_arg[0] = "["
                default_arg[-1] = "]"
                args_info[-(index + 1)] = "".join(default_arg)
        if args_spec.varargs:  # Compensate for *args
            args_info.append("<" + args_spec.varargs + ">")
        if args_spec.kwonlyargs:
            args_info.extend(["<" + a + ">" for a in args_spec.kwonlyargs])
        args_info.insert(0, self.bot.command_prefix + command.name)  # Add command name to the front
        return " ".join(args_info)  # Return args

        args = inspect.getfullargspec(command.callback)
        args_info = {}
        for arg in args[0][2:] + args[4]:
            if arg not in args[6]:
                args_info[arg] = None
            else:
                args_info[arg] = args[6][arg].__name__
        usage = " ".join("<{}: {}>".format(k, v) if v is not None else "<{}>".format(k) for k, v in args_info.items())
        return " ".join([command.name, usage])

    @commands.command(aliases=["h"])
    async def help(self, ctx, cmd=None):
        """Display a list of bot commands."""
        if cmd is None:
            help_embed = discord.Embed(title="Commands are listed below", colour=EMBED_ACCENT_COLOUR)
            help_embed.__setattr__("description", "Type `{}help <command>` for more information".format(self.bot.command_prefix))
            help_embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url_as(format='png', static_format='png'))
            help_embed.set_thumbnail(url=self.bot.user.avatar_url_as(format='png', static_format='png'))
            for cog_name, cog in self.bot.cogs.items():
                cmds = cog.get_commands()
                if cmds:
                    help_embed.add_field(name=cog_name, value="\n".join("`{0.name}`".format(c) for c in cmds if not c.hidden))
            await ctx.author.send(embed=help_embed)
            await ctx.message.add_reaction("\U0001F4EC")
        else:
            command = self.bot.get_command(cmd)
            if command is None:
                ctx.send("That command does not exist")
            else:
                help_embed = discord.Embed(title=command.name, colour=EMBED_ACCENT_COLOUR)
                desc = command.description
                help_embed.description = desc if desc != "" else command.callback.__doc__
                aliases = ", ".join("`{}`".format(c) for c in command.aliases)
                if len(aliases) > 0:
                    help_embed.add_field(name="Aliases", value=aliases)
                usage = self.get_usage(command)
                help_embed.add_field(name="Usage", value="`" + usage + "`")
                await ctx.send(embed=help_embed)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, plugin):
        """Reload a specific plugin"""
        self.bot.reload_extension(plugin)

    @commands.command()
    async def ping(self, ctx):
        """Pong!"""
        pong_msg = await ctx.send(":ping_pong:  pong!")
        diff = pong_msg.created_at - ctx.message.created_at
        ms = int(diff.total_seconds() * 1000)
        await pong_msg.edit(content=":ping_pong:  pong! `{}ms`".format(ms))

    @commands.command(description="Shows how long I've been online for")
    async def uptime(self, ctx):
        """View how long that bot has been online for."""
        uptime = datetime.datetime.utcnow() - self.bot.start_time
        s = uptime.total_seconds()
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        d, h, m, s = map(int, (d, h, m, s))
        uptime_embed = discord.Embed(description=":clock5:  **Ive been online for:**  {}d {}h {}m {}s".format(d, h, m, s), colour=EMBED_ACCENT_COLOUR)
        await ctx.send(embed=uptime_embed)

    @commands.command(name="eval", hidden=True)
    @commands.is_owner()
    async def _eval(self, ctx, *, code):
        """Evaluate Python code"""
        try:
            if code.startswith("await "):
                response = await eval(code.replace("await ", ""))
            else:
                response = eval(code)
            if response is not None:
                await ctx.send("```python\n{}```".format(response))
        except Exception as e:
            await ctx.send("```python\n{}```".format(e))

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exception):
        if type(exception) == discord.ext.commands.errors.CommandNotFound:
            return
        if type(exception) == discord.ext.commands.errors.CheckFailure:
            return
        error_embed = discord.Embed(colour=0xFF0000)
        if type(exception) == discord.ext.commands.errors.MissingRequiredArgument:
            arg = str(exception).split()[0]
            error_embed.title = "Syntax Error"
            error_embed.description = "Usage: `{}`".format(self.get_usage(ctx.command))
            error_embed.set_footer(text="{} is a required argument".format(arg))
        elif type(exception) == discord.ext.commands.errors.BadArgument:
            error_embed.title = "Syntax Error"
            error_embed.description = "Usage: `{}`".format(self.get_usage(ctx.command))
            error_embed.set_footer(text=str(exception))
        else:
            error_embed.title = "Error"
            error_embed.description = "`" + str(exception).split(":")[-1] + "`"
        if error_embed.description is not None:
            return await ctx.send(embed=error_embed)

    @commands.Cog.listener()
    async def on_ready(self):
        game = discord.Activity(name="the server", type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=game)


class Watson(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def rep(self, ctx, member: discord.Member):
        """Add a reputation point to a member."""
        if member.bot:
            raise Exception("You can't rep a bot!")
        elif member == ctx.author:
            raise Exception("You can't rep yourself!")

        reps = self.bot.database.add_rep(member)
        await ctx.send(f"✅ **{member.mention}** now has `{reps}` reputation points!")

    @commands.command()
    @commands.guild_only()
    async def repcount(self, ctx, member: discord.Member=None):
        """View how many reputation points a user has."""
        if member is None:
            member = ctx.author
        rep_count = self.bot.database.get_reps(member)
        await ctx.send(f"{member} has `{rep_count}` reputation points.")

    @commands.command()
    async def leaderboard(self, ctx):
        """View the reputation points leaderboard."""
        leaderboard = self.bot.database.get_top_reps()
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR)
        embed.set_author(name="Reputation Leaderboard", icon_url="https://images.emojiterra.com/mozilla/512px/1f3c6.png")
        for member_id, points in leaderboard:
            member = ctx.guild.get_member(member_id)
            if member:
                embed.add_field(name=str(member), value=points, inline=False)
        await ctx.send(embed=embed)
            

class Moderation(commands.Cog):

    BAN = "b"
    MUTE = "m"

    def __init__(self, bot):
        self.bot = bot
        self.check_expired_punishments.start()

    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def reps(self, ctx, *, query: str=None):
        """Configure the reputation points. (Admin only)
        
        Command options:
        -reps set <member> <amount>
        -reps remove <member> <amount>
        -reps add <member> <amount>
        -reps clear"""
        if query is not None:
            args = [a.strip() for a in query.split()]
            if args[0].lower() in ["set", "remove", "add"]:
                if len(args) != 3:
                    raise Exception("Invalid options.")
                member = ctx.guild.get_member_named(args[1])
                if not member and not ctx.message.mentions:
                    raise Exception("Member not found")
                elif not member:
                    member = ctx.message.mentions[0]
                amount = args[2]
                if not amount.isdigit():
                    raise Exception("Amount must be an integer")
                amount = int(amount)

                if args[0].lower() == "set":
                    new_points = self.bot.database.set_reps(member, amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} set {member.mention}'s reputation points to {new_points}")
                elif args[0].lower() == "remove":
                    new_points = self.bot.database.add_rep(member, amount=-amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} removed {amount} reputation points from {member.mention}")
                elif args[0].lower() == "add":
                    new_points = self.bot.database.add_rep(member, amount=amount)
                    embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                          description=f"🏅 {ctx.author.mention} added {amount} reputation points from {member.mention}")
                await self.log(embed)
                await ctx.send(f"✅ **{member}** now has `{new_points}` reputation points!")
            elif args[0].lower() == "clear":
                await self.remove_all_reps(ctx)

    async def remove_all_reps(self, ctx):
        temp = await ctx.send("⛔ **You are about to completely remove all reputation points from everyone in the server**\n"
                              "\nTo confirm this action, please type `confirm` within the next 10 seconds.")
        
        def check(m):
            return m.content == "confirm" and m.author == ctx.author and m.channel == ctx.channel
        
        try:
            response = await self.bot.wait_for("message", check=check, timeout=10)
        except asyncio.TimeoutError:
            return
        else:
            self.bot.database.clear_reputations()
            embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, 
                                  description=f"🏅 {ctx.author.mention} removed ALL reputation points")
            await self.log(embed)
            await response.delete()
            await ctx.send("✅ All reputation points have been cleared.")
            if ctx.author != ctx.guild.owner:
                await ctx.guild.owner.send("**Notice:** All reputation points have been cleared from the server\n"
                                           f"\nThis action was carried out by {ctx.author} (`{ctx.author.id}`)")
        finally:
            await temp.delete()
    
    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
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
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(kick_members=True)
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
                date = datetime.datetime.fromtimestamp(last_warning[2])
                embed.add_field(name=f"{n}. {date.strftime('%d %B %Y')}",
                                value=f"Reason: {reason}\n"
                                      f"Given by: {ctx.guild.get_member(author_id)}", inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"{member} has no previous warnings.")

    @commands.command(aliases=["removewarn", "warnremove"])
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(manage_messages=True)
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
    @commands.has_permissions(ban_members=True)
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
    @commands.has_permissions(manage_messages=True)
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
    @commands.has_permissions(manage_messages=True)
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
    @commands.has_permissions(administrator=True)
    async def muterole(self, ctx, role: discord.Role):
        """Set the mute role."""
        text_overwrite = discord.PermissionOverwrite(send_messages=False)
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
    @commands.has_permissions(kick_members=True)
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
    @commands.has_permissions(administrator=True)
    async def logchannel(self, ctx, channel: discord.TextChannel):
        """Set the channel in which logs are sent."""
        self.bot.database.set_setting("log_guild_id", str(channel.guild.id))
        self.bot.database.set_setting("log_channel_id", str(channel.id))
        await ctx.send(f"✅ {channel.mention} is now the log channel.")

    @tasks.loop(minutes=1, reconnect=True)
    async def check_expired_punishments(self):
        print('Checking for expired punishments')
        punishments = self.bot.database.get_expired_punishments()
        if punishments:
            print('Punishments found, Removing them.')
        for p in punishments:
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
    bot.add_cog(General(bot))
    bot.add_cog(Watson(bot))
    bot.add_cog(Moderation(bot))
