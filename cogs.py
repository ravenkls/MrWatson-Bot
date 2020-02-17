import inspect
import asyncio

import discord
from discord.ext import commands

from settings import *


def server_channel(ctx):
    return not isinstance(ctx.channel, discord.DMChannel)


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
        """Reload all plugins or a specific plugin"""
        self.bot.reload_extension(plugin)

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


class Helpers(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(server_channel)
    async def rep(self, ctx, member: discord.Member):
        """Add a reputation point to a member."""
        if member.bot:
            raise Exception("You can't rep a bot!")
        elif member == ctx.author:
            raise Exception("You can't rep yourself!")

        reps = self.bot.database.add_rep(member)
        await ctx.send(f"✅ **{member.mention}** now has `{reps}` reputation points!")

    @commands.command()
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
        
    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def reps(self, ctx, *, query: str=None):
        """Configure the reputation points. (Admin only)
        
        Command options:
        -reps set <member> <amount>
        -reps remove <member> <amount>
        -reps add <member> <amount>
        -reps clear"""
        if query is not None:
            args = query.split(" ")
            if query[0] in ["set", "remove", "add"]:
                if len(query) != 3:
                    raise Exception("Invalid options.")
                member = ctx.guild.get_member_named(self.query[1])
                if not member:
                    raise Exception("Member not found")
                amount = query[2]
                if not amount.isdigit():
                    raise Exception("Amount must be an integer")
                amount = int(amount)

                if query[0] == "set":
                    self.bot.database.set_reps(member, amount)
                    new_points = amount
                elif query[0] == "remove":
                    new_points = self.bot.database.add_rep(member, amount=-amount)
                elif query[0] == "add":
                    new_points = self.bot.database.add_rep(member, amount=amount)
                        
                await ctx.send(f"✅ **{member}** now has `{new_points}` reputation points!")
            else:
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
            await response.delete()
            await ctx.send("✅ All reputation points have been cleared.")
            if ctx.author != ctx.guild.owner:
                await ctx.guild.owner.send("**Notice:** All reputation points have been cleared from the server\n"
                                           f"\nThis action was carried out by {ctx.author} (`{ctx.author.id}`)")
        finally:
            await temp.delete()

def setup(bot):
    bot.add_cog(General(bot))
    bot.add_cog(Helpers(bot))
