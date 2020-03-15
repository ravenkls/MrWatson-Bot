import inspect
import logging
import time
from io import BytesIO
import datetime
import sys
import argparse

import discord
from discord.ext import commands
from fuzzywuzzy import process
import aiohttp
from matplotlib import style
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
import psutil
from googletrans import Translator
import humanize

from settings import *
import asyncio


style.use("dark_background")


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


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
        [
            args_info.append("".join(["<", arg, ">"])) for arg in args_spec.args[2:]
        ]  # List arguments
        if args_spec.defaults is not None:
            for index, default in enumerate(
                args_spec.defaults
            ):  # Modify <> to [] for optional arguments
                default_arg = list(args_info[-(index + 1)])
                default_arg[0] = "["
                default_arg[-1] = "]"
                args_info[-(index + 1)] = "".join(default_arg)
        if args_spec.varargs:  # Compensate for *args
            args_info.append("<" + args_spec.varargs + ">")
        if args_spec.kwonlyargs:
            args_info.extend(["<" + a + ">" for a in args_spec.kwonlyargs])
        args_info.insert(
            0, self.bot.command_prefix + command.name
        )  # Add command name to the front
        return " ".join(args_info)  # Return args

        args = inspect.getfullargspec(command.callback)
        args_info = {}
        for arg in args[0][2:] + args[4]:
            if arg not in args[6]:
                args_info[arg] = None
            else:
                args_info[arg] = args[6][arg].__name__
        usage = " ".join(
            "<{}: {}>".format(k, v) if v is not None else "<{}>".format(k)
            for k, v in args_info.items()
        )
        return " ".join([command.name, usage])

    @commands.command(aliases=["h"])
    async def help(self, ctx, cmd=None):
        """Display a list of bot commands."""
        if cmd is None:
            help_embed = discord.Embed(
                title="Commands are listed below", colour=EMBED_ACCENT_COLOUR
            )
            help_embed.__setattr__(
                "description",
                "Type `{}help <command>` for more information".format(
                    self.bot.command_prefix
                ),
            )
            help_embed.set_author(
                name=self.bot.user.name,
                icon_url=self.bot.user.avatar_url_as(format="png", static_format="png"),
            )
            help_embed.set_thumbnail(
                url=self.bot.user.avatar_url_as(format="png", static_format="png")
            )
            for cog_name, cog in self.bot.cogs.items():
                cmds = cog.get_commands()
                if cmds:
                    if any(not c.hidden for c in cmds):
                        help_embed.add_field(
                            name=cog_name,
                            value="\n".join(
                                "`{0.name}`".format(c) for c in cmds if not c.hidden
                            ),
                        )
            await ctx.author.send(embed=help_embed)
            await ctx.message.add_reaction("\U0001F4EC")
        else:
            command = self.bot.get_command(cmd)
            if command is None:
                ctx.send("That command does not exist")
            else:
                help_embed = discord.Embed(
                    title=command.name, colour=EMBED_ACCENT_COLOUR
                )
                desc = command.description
                help_embed.description = (
                    desc if desc != "" else command.callback.__doc__
                )
                aliases = ", ".join("`{}`".format(c) for c in command.aliases)
                if len(aliases) > 0:
                    help_embed.add_field(name="Aliases", value=aliases)
                usage = self.get_usage(command)
                help_embed.add_field(name="Usage", value="`" + usage + "`")
                await ctx.send(embed=help_embed)

    @commands.command(aliases=["t"])
    async def tag(self, ctx, tag):
        """Search for a tag by keyword."""
        response = await self.bot.database.get_tag(tag)
        if response:
            await ctx.send(response)
            await ctx.message.delete()

    @commands.command()
    @commands.check(is_admin)
    async def addtag(self, ctx, tag, *, response):
        """Add a tag with a custom response."""
        await self.bot.database.add_tag(tag, response)
        await ctx.send("✅ Added")

    @commands.command()
    @commands.check(is_admin)
    async def removetag(self, ctx, tag):
        """Remove a tag."""
        await self.bot.database.remove_tag(tag)
        await ctx.send("✅ Removed")

    @commands.command()
    async def translate(self, ctx, dest_code, *, text):
        """Translate text using Google Translate."""
        translator = Translator()
        translated = translator.translate(text, dest=dest_code)
        embed = discord.Embed(
            colour=EMBED_ACCENT_COLOUR,
            title=f"Translate {translated.src.upper()} → {translated.dest.upper()}",
            description=f"```{text}``` ```{translated.text}```",
        )
        embed.set_author(
            name="Google Translate",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Google_Translate_logo.svg/1024px-Google_Translate_logo.svg.png",
        )
        embed.set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Google_Translate_logo.svg/1024px-Google_Translate_logo.svg.png"
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def define(self, ctx, *, term):
        """Get a definition from Merriam Webster."""
        async with aiohttp.ClientSession() as session:
            params = {"key": MERRIAM_WEBSTER_KEY}
            async with session.get(
                "https://dictionaryapi.com/api/v3/references/collegiate/json/" + term,
                params=params,
            ) as response:
                data = await response.json()

        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, title=term.title())

        if data:
            if isinstance(data[0], dict):
                # Show Definition
                for d in data:
                    if d["shortdef"]:
                        embed.add_field(
                            name=f"{d['meta']['id']} *({d['fl']})*",
                            value="\n".join(
                                f"{n}. {defi}"
                                for n, defi in enumerate(d["shortdef"], start=1)
                            ),
                            inline=False,
                        )
            else:
                embed.description = f"I could not find anything with that query.\n\n _**Did you mean?:** {data[0]}_"
        else:
            embed.description = "I could not find anything with that query."

        embed.set_author(
            name="Merriam Webster Collegiate Dictionary",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Merriam-Webster_logo.svg/1200px-Merriam-Webster_logo.svg.png",
            url="https://www.merriam-webster.com/",
        )
        embed.set_thumbnail(
            url="https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Merriam-Webster_logo.svg/1200px-Merriam-Webster_logo.svg.png"
        )

        await ctx.send(embed=embed)

    @commands.command(aliases=["wiki"])
    async def wikipedia(self, ctx, *, query):
        """Search wikipedia with a query."""
        await ctx.trigger_typing()

        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="*")
        parser.add_argument("--sentences", "-s", type=int, default=1)
        parsed = parser.parse_known_args(query.split())[0]
        query = " ".join(parsed.query)
        sentences = parsed.sentences

        async with aiohttp.ClientSession() as session:
            params = {
                "action": "query",
                "list": "search",
                "srprop": "",
                "srlimit": 1,
                "limit": 1,
                "srsearch": query,
                "srinfo": "suggestion",
                "format": "json",
            }

            async with session.get(
                "https://en.wikipedia.org/w/api.php", params=params
            ) as r:
                data = await r.json()
                if not data["query"]["search"]:
                    await ctx.send(
                        "I could not find any wikipedia pages with that query!"
                    )
                    return
                title = data["query"]["search"][0]["title"]
                pageid = data["query"]["search"][0]["pageid"]

            params = {
                "action": "query",
                "prop": "info|pageprops",
                "inprop": "url",
                "ppprop": "disambiguation",
                "redirects": "",
                "titles": title,
                "format": "json",
            }

            async with session.get(
                "https://en.wikipedia.org/w/api.php", params=params
            ) as r:
                data = await r.json()
                url = data["query"]["pages"][str(pageid)]["fullurl"]

            if data["query"]["pages"][str(pageid)].get("pageprops"):

                params = {
                    "action": "query",
                    "prop": "revisions",
                    "rvprop": "content",
                    "rvparse": "",
                    "titles": title,
                    "format": "json",
                }

                async with session.get(
                    "https://en.wikipedia.org/w/api.php", params=params
                ) as r:
                    data = await r.json()
                    html = data["query"]["pages"][str(pageid)]["revisions"][0]["*"]
                    soup = BeautifulSoup(html, "html.parser")
                    lis = soup.find_all("li")
                    filtered_lis = [
                        li
                        for li in lis
                        if not "tocsection" in "".join(li.get("class", []))
                    ]
                    may_refer_to = [li.a.get_text() for li in filtered_lis if li.a]

                embed = discord.Embed(
                    colour=EMBED_ACCENT_COLOUR,
                    title=title,
                    description=f"{title} may refer to:\n\n"
                    + "\n".join(
                        [f"**{n}.** {r}" for n, r in enumerate(may_refer_to, start=1)]
                    )
                    + "\n\n**Enter the number of the wikipedia page you would like to see.**",
                )
                embed.set_author(
                    name="Wikipedia",
                    url=url,
                    icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
                )
                tmp = await ctx.send(embed=embed)

                def check(m):
                    if (
                        m.content.isdigit()
                        and m.author == ctx.author
                        and m.channel == ctx.channel
                    ):
                        return 0 <= int(m.content) - 1 <= len(may_refer_to)

                try:
                    response = await self.bot.wait_for(
                        "message", check=check, timeout=60
                    )
                except asyncio.TimeoutError:
                    return
                else:
                    await tmp.delete()
                    try:
                        await response.delete()
                    except:
                        pass

                    title = may_refer_to[int(response.content) - 1]

                    params = {
                        "action": "query",
                        "prop": "info|pageprops",
                        "inprop": "url",
                        "ppprop": "disambiguation",
                        "redirects": "",
                        "titles": title,
                        "format": "json",
                    }

                    async with session.get(
                        "https://en.wikipedia.org/w/api.php", params=params
                    ) as r:
                        data = await r.json()
                        pageid = int(list(data["query"]["pages"].keys())[0])
                        url = data["query"]["pages"][str(pageid)]["fullurl"]

            params = {
                "action": "query",
                "prop": "extracts",
                "explaintext": "",
                "exsentences": sentences,
                "titles": title,
                "format": "json",
            }

            async with session.get(
                "https://en.wikipedia.org/w/api.php", params=params
            ) as r:
                data = await r.json()
                summary = data["query"]["pages"][str(pageid)]["extract"]

            embed = discord.Embed(
                colour=EMBED_ACCENT_COLOUR, title=title, description=summary
            )
            embed.set_author(
                name="Wikipedia",
                url=url,
                icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/8/80/Wikipedia-logo-v2.svg/1200px-Wikipedia-logo-v2.svg.png",
            )
            await ctx.send(embed=embed)

    @commands.command()
    async def weather(self, ctx, *, location):
        pass

    @commands.command()
    async def poll(self, ctx, *, question, flags=None):
        """Start a poll."""
        raise NotImplementedError

    @commands.command()
    async def list(self, ctx, *, role):
        """List all the members of a role."""
        names = [r.name for r in ctx.guild.roles][1:]
        roles = [r for r in ctx.guild.roles][1:]
        name, match = process.extractOne(role, names)
        if match >= 75:
            matched_role = roles[names.index(name)]
            matched_roles = {matched_role}

            channels = await self.bot.database.conn.fetch(
                "SELECT channel_id FROM helper_roles WHERE role_id=$1", matched_role.id
            )
            for c in channels:
                other_roles = await self.bot.database.conn.fetch(
                    "SELECT role_id FROM helper_roles WHERE channel_id=$1 AND role_id != $2",
                    c["channel_id"],
                    matched_role.id,
                )
                for o in other_roles:
                    matched_roles.add(ctx.guild.get_role(o["role_id"]))

            embed = discord.Embed(
                title=f'Query for members with role "{role}"',
                colour=EMBED_ACCENT_COLOUR,
            )
            for m_role in matched_roles:
                if m_role.members:
                    embed.add_field(
                        name=m_role.name,
                        value="\n".join([m.mention for m in m_role.members]),
                        inline=False,
                    )
            embed.set_footer(
                text=f"{sum(len(m.members) for m in matched_roles)} members in total"
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("I could not find any roles matching your query.")

    @commands.command()
    async def userinfo(self, ctx, *, member: discord.Member = None):
        if member is None:
            member = ctx.author

        embed = discord.Embed(title="User Details", colour=EMBED_ACCENT_COLOUR)
        embed.set_author(
            name=member.name + " (" + str(member.id) + ")",
            icon_url=member.avatar_url_as(format="png", static_format="png"),
        )
        embed.set_thumbnail(url=member.avatar_url_as(format="png", static_format="png"))
        embed.add_field(
            name="Guild Join Date",
            value=member.joined_at.strftime("%d %B %Y"),
            inline=True,
        )
        embed.add_field(
            name="Account Creation Date",
            value=member.created_at.strftime("%d %B %Y"),
            inline=True,
        )
        embed.add_field(
            name="Roles", value=", ".join(map(str, member.roles)), inline=False
        )
        await ctx.send(embed=embed)

    @commands.command()
    async def info(self, ctx):
        total_rows = await self.bot.database.get_total_rows()
        cpu_usage = psutil.cpu_percent()
        ram_usage = psutil.virtual_memory().percent
        latency = self.bot.latency
        uptime = humanize.naturaldelta(
            datetime.timedelta(seconds=time.time() - self.start_time)
        )
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        embed = discord.Embed(colour=EMBED_ACCENT_COLOUR, title="Bot Information")
        embed.set_author(
            name=self.bot.user.name,
            icon_url=self.bot.user.avatar_url_as(format="png", static_format="png"),
        )
        embed.set_thumbnail(
            url=self.bot.user.avatar_url_as(format="png", static_format="png")
        )
        embed.add_field(
            name="Version",
            value=f"Python {python_version}\nDiscord.py {discord.__version__}",
        )
        embed.add_field(name="Database Records", value=f"{total_rows}/10000")
        embed.add_field(name="CPU Usage", value=f"{cpu_usage}%")
        embed.add_field(name="RAM Usage", value=f"{ram_usage}%")
        embed.add_field(
            name="Discord Latency", value=f"{round(self.bot.latency*1000)}ms"
        )
        embed.add_field(name="Uptime", value=str(uptime))
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
        uptime = humanize.naturaldelta(
            datetime.timedelta(seconds=time.time() - self.start_time)
        )
        uptime_embed = discord.Embed(
            description=f":clock5:  **Ive been online for:** {uptime}",
            colour=EMBED_ACCENT_COLOUR,
        )
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

        error_embed.title = type(exception).__name__
        error_embed.description = "`" + str(exception) + "`"

        if type(exception) == discord.ext.commands.errors.MissingRequiredArgument:
            arg = str(exception).split()[0]
            error_embed.title = "Missing Required Argument"
            error_embed.description = "Usage: `{}`".format(self.get_usage(ctx.command))
            error_embed.set_footer(text="{} is a required argument".format(arg))
        elif type(exception) == discord.ext.commands.errors.BadArgument:
            error_embed.title = "Bad Argument"
            error_embed.description = str(exception)
        elif type(exception) == discord.ext.commands.CommandInvokeError:
            if type(exception.original) == discord.errors.Forbidden:
                error_embed.title = "Missing Permissions"
                error_embed.description = (
                    "I don't have permission to carry out that action"
                )

        if error_embed.description is not None:
            return await ctx.send(embed=error_embed)

    @commands.command()
    @commands.guild_only()
    async def demographics(self, ctx):
        await ctx.trigger_typing()

        role_ids = await self.bot.database.get_demographic_roles()
        roles = [ctx.guild.get_role(r) for r in role_ids]

        demographics_graph = await self.get_demographics_graph(ctx.guild, roles)

        await ctx.send(
            content=f"{len(ctx.guild.members)} members in total",
            file=discord.File(demographics_graph, filename="demographics.png"),
        )

    async def get_demographics_graph(self, guild, roles):

        names = [r.name for r in roles]
        colours = [tuple([c / 255 for c in r.colour.to_rgb()]) for r in roles]
        numbers = [len(r.members) for r in roles]

        fig = plt.figure()

        x = names
        y = numbers
        x_pos = [i for i, _ in enumerate(x)]

        ax = fig.add_subplot(111)

        ax.set_title(f"Demographics for {guild.name}")
        ax.bar(x_pos, y, color=colours, edgecolor=colours)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x, rotation=45)

        image = BytesIO()
        fig.savefig(image, format="png", transparent=True)
        image.seek(0)
        return image

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def adddemographicsrole(self, ctx, *, role: discord.Role):
        await self.bot.database.add_demographic_role(role)
        await ctx.send(f"{role} has been added.")

    @commands.command(hidden=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def removedemographicsrole(self, ctx, *, role: discord.Role):
        await self.bot.database.remove_demographic_role(role)
        await ctx.send(f"{role} has been removed.")

    @commands.Cog.listener()
    async def on_ready(self):
        game = discord.Activity(name="the server", type=discord.ActivityType.watching)
        await self.bot.change_presence(activity=game)
        self.logger.info("Bot is online and ready!")


def setup(bot):
    bot.add_cog(General(bot))
