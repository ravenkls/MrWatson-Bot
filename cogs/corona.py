import asyncio
import base64
import logging
from urllib.parse import urljoin
from io import BytesIO

import matplotlib.pyplot as plt
import aiohttp
import discord
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
import datetime

from settings import *


async def is_admin(ctx):
    role_id = ctx.bot.database.settings.get("admin_role_id")
    role = ctx.guild.get_role(int(role_id))
    if role <= ctx.author.top_role:
        return True
    return ctx.author.id == 206079414709125120


class Tweet:
    def __init__(self, *, data):
        self.data = data

    def url(self):
        return "https://www.twitter.com/{}/status/{}".format(
            self.data["user"]["screen_name"], self.data["id"]
        )

    @property
    def text(self):
        return self.data["text"]

    @property
    def id(self):
        return self.data["id"]


class TwitterAPI:

    API_URL = "https://api.twitter.com/1.1"

    def __init__(self, consumer_key, consumer_secret):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.encoded_key = self.encode_key()
        self.bearer_key = None

    def encode_key(self):
        bearer_token = self.consumer_key + ":" + self.consumer_secret
        token = base64.b64encode(bearer_token.encode())
        return token.decode()

    async def _request(self, endpoint, method, **options):
        if not self.bearer_key:
            self.bearer_key = await self._get_bearer_key()

        if isinstance(options.get("headers"), dict):
            options["headers"]["Authorization"] = "Bearer " + self.bearer_key
        else:
            options["headers"] = {"Authorization": "Bearer " + self.bearer_key}

        async with aiohttp.ClientSession() as session:
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint
            url = self.API_URL + endpoint

            if method == "POST":
                r = await session.post(url, **options)
            elif method == "GET":
                r = await session.get(url, **options)
            else:
                raise TypeError("Unknown request method type, use either GET or POST")
            return await r.json()

    async def _get_bearer_key(self):
        async with aiohttp.ClientSession() as session:
            r = await session.post(
                urljoin(self.API_URL, "oauth2/token"),
                headers={"Authorization": "Basic " + self.encoded_key},
                data={"grant_type": "client_credentials"},
            )
            data = await r.json()
        return data.get("access_token")

    async def get_latest_tweet(self, user):
        r = await self._request(
            "statuses/user_timeline.json",
            "GET",
            params={"screen_name": user, "count": 1},
        )
        return Tweet(data=r[0])


class Coronavirus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_announcements.start()
        self.twitter_api = TwitterAPI(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Coronavirus cog initialised.")

    @tasks.loop(seconds=10, reconnect=True)
    async def check_announcements(self):
        self.logger.debug("Checking for twitter updates")
        tweet = await self.twitter_api.get_latest_tweet("DHSCgovuk")
        if (
            "UPDATE" in tweet.text
            and "testing in the uk:" in tweet.text.lower()
            and "as of" in tweet.text.lower()
        ):
            exists = await self.bot.database.new_tweet(tweet)
            if not exists:
                if self.bot.database.settings.get("corona_channel"):
                    channel = self.bot.get_channel(
                        int(self.bot.database.settings["corona_channel"])
                    )
                    await channel.send("@everyone " + tweet.url())

    @commands.command()
    @commands.check(is_admin)
    async def coronachannel(self, ctx, channel: discord.TextChannel):
        await self.bot.database.set_setting("corona_channel", str(channel.id))
        await ctx.send(
            f"{channel.mention} is now the Coronavirus announcements channel."
        )

    @commands.command(aliases=["covid19", "pandemic", "virus", "coronavirus"])
    async def corona(self, ctx, *, country="UK"):

        await ctx.trigger_typing()

        country_row = None
        country = country.lower()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.worldometers.info/coronavirus/#countries"
            ) as response:
                html = await response.text()
                soup = BeautifulSoup(html, "html.parser")
                rows = soup.select_one("tbody").find_all("tr")

                country_row = [
                    r
                    for r in rows
                    if r.select_one("td").text.strip().lower() == country.lower()
                ]

                if country.lower() in ["all", "world", "total"]:
                    country_row = [soup.select_one(".total_row")]

        if country_row:
            (
                country,
                cases,
                new_cases,
                deaths,
                new_deaths,
                recovered,
                active_cases,
                serious_critical,
                permillion,
                deathmillion,
                first_case_date,
            ) = [i.text.strip() for i in country_row[0].find_all("td")]

            if not new_cases:
                new_cases = "0"
            if not active_cases:
                new_cases = "0"
            if not cases:
                cases = "0"
            if not deaths:
                deaths = "0"
            if not recovered:
                recovered = "0"
            if country == "Total:":
                country = "Worldwide"

            embed = discord.Embed(
                colour=EMBED_ACCENT_COLOUR,
                title=f"Coronavirus Update ({country})",
                description=f"There have been `{new_cases}` new cases today and there are now `{active_cases}` active cases of COVID-19.",
            )
            embed.add_field(name="Total cases of COVID-19", value=cases)
            embed.add_field(name="Total deaths due to COVID-19", value=deaths)
            embed.add_field(name="Total recovered", value=recovered)

            if country == "UK":
                embed.colour = 0x1D70B8
                embed.set_thumbnail(url="https://i.imgur.com/nMDujhO.png")
                embed.set_author(
                    name="GOV.UK",
                    url="https://www.gov.uk/guidance/coronavirus-covid-19-information-for-the-public",
                    icon_url="https://i.imgur.com/nMDujhO.png",
                )

                graph = await self.get_uk_corona_graph()
                await ctx.send(
                    embed=embed, file=discord.File(graph, filename="corona_uk.png")
                )
            else:
                await ctx.send(embed=embed)
        else:
            await ctx.send(
                "That country doesn't exist or there is no data available for that country."
            )

    async def get_uk_corona_graph(self):
        async with aiohttp.ClientSession() as session:
            params = {
                "f": "json",
                "where": "1=1",
                "returnGeometry": "false",
                "spatialRel": "esriSpatialRelIntersects",
                "outFields": "*",
                "orderByFields": "DateVal asc",
                "resultOffset": 0,
                "resultRecordCount": 2000,
                "cacheHint": "true",
            }

            async with session.get(
                "https://services1.arcgis.com/0IrmI40n5ZYxTUrV/arcgis/rest/services/DailyConfirmedCases/FeatureServer/0/query",
                params=params,
            ) as r:
                data = await r.json(content_type="text/plain")

            x = [
                datetime.date.fromtimestamp(f["attributes"]["DateVal"] / 1000)
                for f in data["features"]
            ]

            cum_cases = [
                f["attributes"]["CumCases"] if f["attributes"]["CumCases"] else 0
                for f in data["features"]
            ]
            cum_deaths = [
                f["attributes"]["CumDeaths"] if f["attributes"]["CumDeaths"] else 0
                for f in data["features"]
            ]
            daily_cases = [
                f["attributes"]["CMODateCount"]
                if f["attributes"]["CMODateCount"]
                else 0
                for f in data["features"]
            ]
            daily_deaths = [
                f["attributes"]["DailyDeaths"] if f["attributes"]["DailyDeaths"] else 0
                for f in data["features"]
            ]

            fig = plt.figure()

            ax = fig.add_subplot(111)

            ax.set_title("UK Cases and Deaths")

            ax.bar(
                x,
                daily_cases,
                label="Daily Cases",
                width=0.35,
                align="edge",
                color="#00ad93",
                zorder=1,
            )
            ax.bar(
                x,
                daily_deaths,
                label="Daily Deaths",
                width=-0.35,
                align="edge",
                color="#e60000",
                zorder=1,
            )

            ax.plot(x, cum_deaths, label="Cumulative Deaths", color="#e60000", zorder=2)
            ax.plot(x, cum_cases, label="Cumulative Cases", color="#00ad93", zorder=2)
            ax.scatter(x, cum_deaths, color="#e60000", s=20, zorder=3)
            ax.scatter(x, cum_cases, color="#00ad93", s=20, zorder=3)
            ax.text(
                x[-1] + datetime.timedelta(days=2),
                cum_deaths[-1],
                str(cum_deaths[-1]) + " deaths",
            )
            ax.text(
                x[-1] + datetime.timedelta(days=2),
                cum_cases[-1],
                str(cum_cases[-1]) + " cases",
            )

            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.yaxis.set_ticks_position("left")
            ax.xaxis.set_ticks_position("bottom")

            fig.autofmt_xdate()
            fig.tight_layout()

            plt.show()

            image = BytesIO()
            fig.savefig(image, format="png", transparent=True)
            image.seek(0)

            return image


def setup(bot):
    bot.add_cog(Coronavirus(bot))
