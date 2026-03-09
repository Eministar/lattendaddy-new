from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.moderation.services.permission_service import PermissionService
from bot.modules.sponsor.services.sponsor_service import SponsorService


class SponsorCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "sponsor_service", None) or SponsorService(bot, bot.settings, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    nebu = app_commands.Group(name="nebu", description="☁️ 𑁉 Nebuliton-Partnerpanel")

    @staticmethod
    def _target_from_channel(
        channel: discord.abc.GuildChannel | discord.Thread | None,
    ) -> discord.TextChannel | discord.Thread | None:
        if isinstance(channel, (discord.TextChannel, discord.Thread)):
            return channel
        return None

    @nebu.command(name="send", description="☁️ 𑁉 Nebuliton-Sponsorpanel senden")
    @app_commands.describe(channel="Optional: Ziel-Channel für das Sponsorpanel")
    async def send(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)

        err = self.permission_service.action_error(interaction.user, "nebu_send")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        target = self._target_from_channel(channel) or self._target_from_channel(interaction.channel)
        if not target:
            return await interaction.response.send_message(
                "Bitte den Befehl in einem Text-Channel oder Thread nutzen.",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.service.send_nebuliton_panel(target, interaction.guild)
        except discord.Forbidden:
            return await interaction.followup.send("Ich kann dort nichts senden.", ephemeral=True)
        except discord.HTTPException:
            return await interaction.followup.send("Das Sponsorpanel konnte nicht gesendet werden.", ephemeral=True)

        await interaction.followup.send(f"Nebuliton-Panel gesendet in {target.mention}.", ephemeral=True)

    @commands.group(name="nebu", invoke_without_command=True)
    async def nebu_prefix(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return
        await ctx.reply("Nutze `!nebu send` oder `/nebu send`.", mention_author=False)

    @nebu_prefix.command(name="send")
    async def nebu_prefix_send(self, ctx: commands.Context, channel: discord.TextChannel | None = None):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return

        err = self.permission_service.action_error(ctx.author, "nebu_send")
        if err:
            return await ctx.reply(err, mention_author=False)

        target = self._target_from_channel(channel) or self._target_from_channel(ctx.channel)
        if not target:
            return await ctx.reply("Bitte nutze den Command in einem Text-Channel oder Thread.", mention_author=False)

        try:
            await self.service.send_nebuliton_panel(target, ctx.guild)
        except discord.Forbidden:
            return await ctx.reply("Ich kann dort nichts senden.", mention_author=False)
        except discord.HTTPException:
            return await ctx.reply("Das Sponsorpanel konnte nicht gesendet werden.", mention_author=False)

        await ctx.reply(f"Nebuliton-Panel gesendet in {target.mention}.", mention_author=False)

