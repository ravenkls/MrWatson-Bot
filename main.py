from discord.ext import commands
from settings import DISCORD_TOKEN
from database import Database
import time
import logging
import os


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.database = Database()
        self.start_time = time.time()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    bot = Bot(command_prefix="-")
    bot.load_extension("cogs")
    bot.run(DISCORD_TOKEN)
