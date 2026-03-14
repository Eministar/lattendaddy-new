from __future__ import annotations

import discord
from discord.ext import commands

from bot.modules.emoji_quiz.services.emoji_quiz_service import EmojiQuizService


class EmojiQuizListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "emoji_quiz_service", None) or EmojiQuizService(bot, bot.settings, bot.db, bot.logger)

    @commands.Cog.listener("on_message")
    async def on_message(self, message: discord.Message):
        await self.service.handle_message(message)
