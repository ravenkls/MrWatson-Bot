from discord.ext import commands
from settings import DISCORD_TOKEN
from database import Database
import time
import logging
import os


class Bot(commands.Bot):
    database = Database()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="[%(levelname)s] [%(name)s] %(message)s"
    )

    bot = Bot(command_prefix="-")
    bot.load_extension("cogs.general")
    bot.load_extension("cogs.helpers")
    bot.load_extension("cogs.assignroles")
    bot.load_extension("cogs.fun")
    bot.load_extension("cogs.events")
    bot.load_extension("cogs.corona")
    bot.run(DISCORD_TOKEN)
