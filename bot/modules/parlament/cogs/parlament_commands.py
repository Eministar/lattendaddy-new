import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.moderation.services.permission_service import PermissionService
from bot.modules.parlament.services.parlament_service import ParliamentService


class ParliamentCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "parlament_service", None) or ParliamentService(bot, bot.settings, bot.db, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    def _action_error(self, interaction: discord.Interaction, action: str) -> str | None:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return "Nur im Server nutzbar."
        return self.permission_service.action_error(interaction.user, action)

    parlament = app_commands.Group(name="parlament", description="🏛️ 𑁉 Parlament")
    start = app_commands.Group(name="start", description="Start", parent=parlament)
    stop = app_commands.Group(name="stop", description="Stop", parent=parlament)
    partei = app_commands.Group(name="partei", description="Partei-System", parent=parlament)

    @start.command(name="vote", description="🗳️ 𑁉 Votum starten")
    async def start_vote(self, interaction: discord.Interaction):
        err = self._action_error(interaction, "parliament_start_vote")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.start_vote(interaction)

    @stop.command(name="vote", description="🛑 𑁉 Votum stoppen")
    async def stop_vote(self, interaction: discord.Interaction):
        err = self._action_error(interaction, "parliament_stop_vote")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.stop_vote(interaction)

    @parlament.command(name="panel", description="📌 𑁉 Parlament-Panel aktualisieren")
    async def panel(self, interaction: discord.Interaction):
        err = self._action_error(interaction, "parliament_panel")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.update_panel(interaction.guild)
        await interaction.response.send_message("Panel aktualisiert.", ephemeral=True)

    @partei.command(name="panel", description="📌 𑁉 Partei-Gründungs-Panel senden")
    async def party_panel(self, interaction: discord.Interaction):
        err = self._action_error(interaction, "parliament_party_panel")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.create_party_panel(interaction)

    @partei.command(name="approve", description="✅ 𑁉 Partei genehmigen")
    @app_commands.describe(party_id="ID der Partei")
    async def party_approve(self, interaction: discord.Interaction, party_id: int):
        err = self._action_error(interaction, "parliament_party_approve")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.approve_party(interaction, int(party_id))

    @partei.command(name="reject", description="❌ 𑁉 Partei ablehnen")
    @app_commands.describe(party_id="ID der Partei", reason="Optionaler Ablehnungsgrund")
    async def party_reject(self, interaction: discord.Interaction, party_id: int, reason: str | None = None):
        err = self._action_error(interaction, "parliament_party_reject")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.reject_party(interaction, int(party_id), reason=reason)

    @partei.command(name="list", description="📋 𑁉 Parteien anzeigen")
    async def party_list(self, interaction: discord.Interaction):
        err = self._action_error(interaction, "parliament_party_list")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.list_parties(interaction)
