import discord
from discord.ext import commands

from bot.modules.debatten.services.debatten_service import DebattenService


class DebattenListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "debatten_service", None) or DebattenService(bot, bot.settings, bot.db, bot.logger)

    @commands.Cog.listener("on_voice_state_update")
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if not member.guild:
            return
        await self.service.handle_voice_state_update(member, before, after)
