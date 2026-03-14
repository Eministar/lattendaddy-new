from __future__ import annotations

import discord
from discord.ext import commands

from bot.modules.guess_the_number.services.guess_number_service import GuessNumberService


class GuessNumberListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "guess_number_service", None) or GuessNumberService(bot, bot.settings, bot.db, bot.logger)

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        await self.service.handle_message(message)
