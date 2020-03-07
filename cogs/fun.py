import argparse
import logging
import re
from io import BytesIO

import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ext import commands


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        self.logger.info("Fun cog initialised.")

    @commands.command()
    async def factoftheday(self, ctx):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://uselessfacts.jsph.pl/today.json?language=en"
            ) as response:
                response = await response.json()

        await ctx.send(response["text"])

    @commands.command()
    async def bttv(self, ctx, *, query):
        """Find a BetterTTV emote with a query."""

        parser = argparse.ArgumentParser()
        parser.add_argument("query", nargs="*")
        parser.add_argument("--addemoji", "-a", action="store_true", default=False)
        parsed = parser.parse_known_args(query.split())[0]

        if parsed.query:
            query = " ".join(parsed.query)
        else:
            query = ""

        async with aiohttp.ClientSession() as session:
            params = {"q": query, "sort": "count-desc"}
            async with session.get(
                "https://www.frankerfacez.com/emoticons/", params=params
            ) as response:
                html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select_one(".emote-table").find_all("tr", class_="selectable")
        emotes = [
            r.select_one(".emote-name").text.lower().strip().split("\n")[0]
            for r in rows
        ]

        try:
            index = emotes.index(query.lower())
        except ValueError:
            return await ctx.send("I could not find any emote with that query.")
        else:
            link = rows[index].select_one(".emote-name.text-left > a")["href"]

        emote_id = re.findall(r"\/emoticon\/(\d+)-", link)
        emoji_name = re.findall(r"\/emoticon\/\d+-(\w+)", link)
        if emote_id:
            emoji_name = emoji_name[0]
            src = f"https://cdn.frankerfacez.com/emoticon/{emote_id[0]}/4"
            async with aiohttp.ClientSession() as session:
                async with session.get(src) as response:
                    data = await response.read()
                    f = discord.File(BytesIO(data), filename="emote.png")

            if parsed.addemoji:
                permission = await is_admin(ctx)
                if permission:
                    await ctx.guild.create_custom_emoji(name=emoji_name, image=data)
                    await ctx.send(f"{emoji_name} is now an emoji")
                else:
                    await ctx.send("You can't add emojis to the server.")
            else:
                await ctx.send(file=f)
        else:
            await ctx.send(
                f"I couldn't parse the emote ID: https://www.frankerfacez.com{link}"
            )


def setup(bot):
    bot.add_cog(Fun(bot))
