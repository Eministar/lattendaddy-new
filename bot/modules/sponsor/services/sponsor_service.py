from __future__ import annotations

import discord

from bot.modules.sponsor.formatting.sponsor_views import build_nebuliton_view


class SponsorService:
    def __init__(self, bot: discord.Client, settings, logger):
        self.bot = bot
        self.settings = settings
        self.logger = logger

    async def send_nebuliton_panel(
        self,
        channel: discord.TextChannel | discord.Thread,
        guild: discord.Guild | None,
    ) -> discord.Message:
        view = build_nebuliton_view(self.settings, guild)
        return await channel.send(view=view)

