from __future__ import annotations

import discord

from bot.modules.sponsor.formatting.sponsor_views import build_nebuliton_embed, build_nebuliton_view


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
        embed = build_nebuliton_embed(self.settings, guild)
        view = build_nebuliton_view()
        return await channel.send(embed=embed, view=view)
