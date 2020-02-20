import inspect
import logging
import time

import discord
from discord.ext import commands
from fuzzywuzzy import process

from settings import *


class General(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command("help")
        self.start_time = time.time()
        self.logger = logging.getLogger(__name__)
        self.logger.info("General cog initialised.")
    
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

    @commands.command()
    async def list(self, ctx, *, role):
        """List all the members of a role."""
        names = [r.name for r in ctx.guild.roles][1:]
        roles = [r for r in ctx.guild.roles][1:]
        name, match = process.extractOne(role, names)
        if match >= 75:
            matched_role = roles[names.index(name)]
            embed = discord.Embed(title=f"Members with the Role {matched_role}",
                                  description="\n".join([m.mention for m in matched_role.members]),
                                  colour=EMBED_ACCENT_COLOUR)
            embed.set_footer(text=f"{len(matched_role.members)} members in total")
            await ctx.send(embed=embed)
        else:
            await ctx.send("I could not find any roles matching your query.")

    @commands.command()
    async def userinfo(self, ctx, *, member: discord.Member=None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(title="User Details", colour=EMBED_ACCENT_COLOUR)
        embed.set_author(name=member.name + " (" + str(member.id) + ")", icon_url=member.avatar_url_as(format='png', static_format='png'))
        embed.set_thumbnail(url=member.avatar_url_as(format='png', static_format='png'))
        embed.add_field(name="Guild Join Date", value=member.joined_at.strftime("%d %B %Y"), inline=True)
        embed.add_field(name="Account Creation Date", value=member.created_at.strftime("%d %B %Y"), inline=True)
        embed.add_field(name="Roles", value=", ".join(map(str, member.roles)), inline=False)
        await ctx.send(embed=embed)
        
    @commands.command(hidden=True)
    @commands.is_owner()
    async def reload(self, ctx, plugin):
        """Reload a specific plugin"""
        self.bot.reload_extension(plugin)

    @commands.command()
    async def ping(self, ctx):
        """Pong!"""
        await ctx.send(f"🏓  pong! `{round(self.bot.latency*1000)}ms`")

    @commands.command(description="Shows how long I've been online for")
    async def uptime(self, ctx):
        """View how long that bot has been online for."""
        s = time.time() - self.start_time
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
            error_embed.description = "`" + str(exception) + "`"
        if error_embed.description is not None:
            return await ctx.send(embed=error_embed)

    @commands.Cog.listener()
    async def on_ready(self):
        game = discord.Activity(name="the server", type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=game)
        self.logger.info("Bot is online and ready!")


def setup(bot):
    bot.add_cog(General(bot))
