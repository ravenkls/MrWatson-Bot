from discord.ext import commands
from settings import DISCORD_TOKEN
from database import Database
import logging
import os


class Bot(commabds.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database = Database()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    bot = Bot(command_prefix="-")
    bot.load_extension("cogs")
    bot.run(DISCORD_TOKEN)
