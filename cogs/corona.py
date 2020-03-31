import asyncio
import base64
import datetime
import logging
from io import BytesIO
from urllib.parse import urljoin

import aiohttp
import discord
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from discord.ext import commands, tasks
import numpy as np

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
        self.last_graph = None
        self.last_graph_id = None
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
                    role = channel.guild.get_role(688844587288100874)
                    await channel.send(f"{role.mention} {tweet.url()}")

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
                active_cases = "0"
            if not cases:
                cases = "0"
            if not new_deaths:
                new_deaths = "0"
            if not deaths:
                deaths = "0"
            if not recovered:
                recovered = "0"
            if not serious_critical:
                serious_critical = "0"
            if not permillion:
                permillion = "0"
            if not deathmillion:
                deathmillion = "0"
            if not first_case_date:
                first_case_date = "0"
            if country == "Total:":
                country = "Worldwide"

            percent_deaths = round(
                (int(deaths.replace(",", "")) / int(cases.replace(",", ""))) * 100, 2
            )
            percent_recovered = round(
                (int(recovered.replace(",", "")) / int(cases.replace(",", ""))) * 100, 2
            )

            embed = discord.Embed(
                colour=EMBED_ACCENT_COLOUR,
                title=f"Coronavirus Update ({country})",
                description=f"There have been `{new_cases}` new cases today and there are now `{active_cases}` active cases of COVID-19.",
            )
            embed.add_field(name="Total Cases", value=cases)
            embed.add_field(name="Total Deaths", value=f"{deaths} ({percent_deaths}%)")
            embed.add_field(
                name="Total Recovered", value=f"{recovered} ({percent_recovered}%)"
            )
            embed.add_field(name="Cases Today", value=new_cases)
            embed.add_field(name="Deaths Today", value=new_deaths)
            embed.add_field(name="Critical", value=serious_critical)
            embed.add_field(name="Cases per Million", value=permillion)
            embed.add_field(name="Deaths per Million", value=deathmillion)

            if country == "UK":
                embed.colour = 0x1D70B8
                embed.set_author(
                    name="GOV.UK",
                    url="https://www.gov.uk/guidance/coronavirus-covid-19-information-for-the-public",
                    icon_url="https://i.imgur.com/nMDujhO.png",
                )
                embed.set_footer(text="Data sourced from Worldometers and GOV.UK")

                data = await self.get_uk_corona_stats()

                cum_cases = data[1]
                pred = self.next_day_prediction(cum_cases)
                day = "Tomorrow" if data[0][-1] == datetime.date.today() else "Today"
                embed.add_field(name=day + "'s Predicted Increase", value=pred)

                graph, graph_id = await self.get_uk_corona_graph(*data)
                graph_image_data = base64.b64encode(graph.getvalue()).decode()
                url = await self.upload_image(graph, graph_id=graph_id)
                embed.set_image(url=url)

                await ctx.send(embed=embed)
            else:
                embed.set_footer(text="Data sourced from Worldometers")
                await ctx.send(embed=embed)
        else:
            await ctx.send(
                "That country doesn't exist or there is no data available for that country."
            )

    def next_day_prediction(self, cases):
        """Prediction is generated using linear regression."""
        y = np.array(cases[-3:])
        x = np.array([1, 2, 3])

        x_bar = np.mean(x)
        x2_bar = np.mean(x ** 2)
        y_bar = np.mean(y)
        xy_bar = np.mean(x * y)

        m = (x_bar * y_bar - xy_bar) / (x_bar ** 2 - x2_bar)
        c = y_bar - m * x_bar

        pred = m * 4 + c

        increase = pred - cases[-1]

        if increase >= 1:
            return "+" + str(int(increase))
        else:
            return str(int(increase))

    async def get_uk_corona_stats(self):
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

            dates = [
                datetime.date.fromtimestamp(f["attributes"]["DateVal"] / 1000)
                for f in data["features"]
            ]

            cum_deaths = []
            cum_cases = []
            for f in data["features"]:
                if f["attributes"]["CumDeaths"]:
                    cum_deaths.append(f["attributes"]["CumDeaths"])
                elif len(cum_deaths):
                    cum_deaths.append(cum_deaths[-1])
                else:
                    cum_deaths.append(0)

                if f["attributes"]["CumCases"]:
                    cum_cases.append(f["attributes"]["CumCases"])
                elif len(cum_deaths):
                    cum_cases.append(cum_cases[-1])
                else:
                    cum_cases.append(0)

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

        return dates, cum_cases, cum_deaths, daily_cases, daily_deaths

    async def get_uk_corona_graph(
        self, dates, cum_cases, cum_deaths, daily_cases, daily_deaths
    ):

        graph_id = cum_cases + cum_deaths

        fig, axes = plt.subplots(2)

        ax1, ax2 = axes

        ax1.set_title("UK Cases and Deaths (Linear)")

        ax1.bar(
            dates,
            daily_cases,
            label="Daily Cases",
            width=0.35,
            align="edge",
            color="#00ad93",
            zorder=1,
        )
        ax1.bar(
            dates,
            daily_deaths,
            label="Daily Deaths",
            width=-0.35,
            align="edge",
            color="#e60000",
            zorder=1,
        )

        ax1.plot(
            dates, cum_deaths, label="Cumulative Deaths", color="#e60000", zorder=2
        )
        ax1.plot(dates, cum_cases, label="Cumulative Cases", color="#00ad93", zorder=2)
        ax1.scatter(dates, cum_deaths, color="#e60000", s=5, zorder=3)
        ax1.scatter(dates, cum_cases, color="#00ad93", s=5, zorder=3)
        ax1.text(
            dates[-1] + datetime.timedelta(days=2),
            cum_deaths[-1],
            str(cum_deaths[-1]) + " deaths",
        )
        ax1.text(
            dates[-1] + datetime.timedelta(days=2),
            cum_cases[-1],
            str(cum_cases[-1]) + " cases",
        )

        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.yaxis.set_ticks_position("left")
        ax1.xaxis.set_ticks_position("bottom")

        ax1.legend(frameon=False)

        ax2.set_title("UK Cases and Deaths (Logarithmic)")
        ax2.set_yscale("log")
        ax2.plot(
            dates, cum_deaths, label="Cumulative Deaths", color="#e60000", zorder=2
        )
        ax2.plot(dates, cum_cases, label="Cumulative Cases", color="#00ad93", zorder=2)
        ax2.scatter(dates, cum_deaths, color="#e60000", s=5, zorder=3)
        ax2.scatter(dates, cum_cases, color="#00ad93", s=5, zorder=3)
        ax2.text(
            dates[-1] + datetime.timedelta(days=2),
            cum_deaths[-1],
            str(cum_deaths[-1]) + " deaths",
        )
        ax2.text(
            dates[-1] + datetime.timedelta(days=2),
            cum_cases[-1],
            str(cum_cases[-1]) + " cases",
        )

        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ax2.yaxis.set_ticks_position("left")
        ax2.xaxis.set_ticks_position("bottom")

        ax2.legend(frameon=False)

        fig.autofmt_xdate()
        fig.tight_layout()

        image = BytesIO()
        fig.savefig(image, format="png", transparent=True)
        image.seek(0)

        return image, graph_id

    async def upload_image(self, file_data, graph_id=None):
        if self.last_graph_id == graph_id:
            return self.last_graph

        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}
            data = {"image": file_data}
            response = await session.post(
                "https://api.imgur.com/3/image", headers=headers, data=data
            )
            response_json = await response.json()
            if response_json["success"]:
                self.last_graph_id = graph_id
                self.last_graph = response_json["data"]["link"]
                return response_json["data"]["link"]


def setup(bot):
    bot.add_cog(Coronavirus(bot))
