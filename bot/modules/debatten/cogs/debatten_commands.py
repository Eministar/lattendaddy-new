from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.debatten.formatting.debatten_embeds import build_notice_embed
from bot.modules.debatten.services.debatten_service import DebattenService
from bot.modules.moderation.services.permission_service import PermissionService


async def _ephemeral(
    interaction: discord.Interaction,
    text: str | None = None,
    embed: discord.Embed | None = None,
):
    if embed is None and text is not None:
        settings = getattr(interaction.client, "settings", None)
        if settings:
            embed = build_notice_embed(settings, interaction.guild, text)
            text = None
        else:
            embed = discord.Embed(title="ℹ️ 𑁉 BKT-DEBATTEN", description=text, color=0xB16B91)
            text = None
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=text, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(content=text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class DebattenCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "debatten_service", None) or DebattenService(bot, bot.settings, bot.db, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    debatte = app_commands.Group(name="debatte", description="🎙️ 𑁉 BKT-Debatten")

    def _need_member(self, interaction: discord.Interaction) -> bool:
        return bool(interaction.guild and isinstance(interaction.user, discord.Member))

    @debatte.command(name="setup", description="⚙️ 𑁉 Debatten-Panel, Review und Podium einrichten")
    @app_commands.describe(
        panel_channel="Channel mit dem Debatten-Panel",
        review_channel="Channel für Anmeldungen und Themeneinsendungen",
        podium_channel="Channel für laufende Debatten",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        review_channel: discord.TextChannel,
        podium_channel: discord.TextChannel,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_setup")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.service.configure(
            interaction.guild,
            panel_channel=panel_channel,
            review_channel=review_channel,
            podium_channel=podium_channel,
        )
        await interaction.edit_original_response(
            embed=build_notice_embed(
                self.bot.settings,
                interaction.guild,
                f"Debatten-System eingerichtet.\n• Panel: {panel_channel.mention}\n• Review: {review_channel.mention}\n• Podium: {podium_channel.mention}",
            )
        )

    @debatte.command(name="panel", description="♻️ 𑁉 Debatten-Panel neu aufbauen")
    async def panel(self, interaction: discord.Interaction):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_panel")
        if err:
            return await _ephemeral(interaction, err)
        await self.service.refresh_panel(interaction.guild, force=True)
        await _ephemeral(interaction, "Das Debatten-Panel wurde aktualisiert.")

    @debatte.command(name="thema-festlegen", description="✅ 𑁉 Bestätigtes politisches Thema direkt anlegen")
    @app_commands.describe(title="Politisches Debattenthema", description="Kurze Beschreibung des Themas")
    async def thema_festlegen(self, interaction: discord.Interaction, title: str, description: str):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_topic_create")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            topic_id = await self.service.create_official_topic(
                interaction.guild,
                interaction.user,
                title=title,
                description=description,
            )
        except ValueError as exc:
            return await _ephemeral(interaction, str(exc))
        await _ephemeral(interaction, f"Bestätigtes Thema erstellt: `#{topic_id}`.")

    @debatte.command(name="thema-annehmen", description="🟢 𑁉 Eingereichtes Thema bestätigen")
    @app_commands.describe(topic_id="Themen-ID", note="Optionale interne Notiz")
    async def thema_annehmen(self, interaction: discord.Interaction, topic_id: int, note: str | None = None):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_topic_approve")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.service.set_topic_status(
            interaction.guild,
            interaction.user,
            topic_id=int(topic_id),
            status="approved",
            review_note=note,
        )
        await _ephemeral(interaction, msg)

    @debatte.command(name="thema-ablehnen", description="🔴 𑁉 Eingereichtes Thema ablehnen")
    @app_commands.describe(topic_id="Themen-ID", note="Optionale Begründung")
    async def thema_ablehnen(self, interaction: discord.Interaction, topic_id: int, note: str | None = None):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_topic_reject")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.service.set_topic_status(
            interaction.guild,
            interaction.user,
            topic_id=int(topic_id),
            status="rejected",
            review_note=note,
        )
        await _ephemeral(interaction, msg)

    @debatte.command(name="themen", description="📚 𑁉 Debatten-Themen anzeigen")
    @app_commands.describe(status="Optionaler Filter")
    @app_commands.choices(status=[
        app_commands.Choice(name="alle", value="all"),
        app_commands.Choice(name="pending", value="pending"),
        app_commands.Choice(name="approved", value="approved"),
        app_commands.Choice(name="rejected", value="rejected"),
    ])
    async def themen(self, interaction: discord.Interaction, status: app_commands.Choice[str] | None = None):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_topic_list")
        if err:
            return await _ephemeral(interaction, err)
        filter_value = None if not status or status.value == "all" else str(status.value)
        embed = await self.service.list_topics_embed(interaction.guild, status=filter_value)
        await _ephemeral(interaction, embed=embed)

    @debatte.command(name="planen", description="🗓️ 𑁉 Debatte terminieren")
    @app_commands.describe(topic_id="Bestätigte Themen-ID", datum="z. B. 30.03.2026 19:30")
    async def planen(self, interaction: discord.Interaction, topic_id: int, datum: str):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_schedule")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.service.plan_debate(
            interaction.guild,
            interaction.user,
            topic_id=int(topic_id),
            scheduled_for_raw=datum,
        )
        await _ephemeral(interaction, msg)

    @debatte.command(name="starten", description="▶️ 𑁉 Geplante Debatte im Podium starten")
    @app_commands.describe(
        event_id="Optionale Event-ID; leer = nächste geplante Debatte",
        sprecher_1="Optionaler Sprecher",
        sprecher_2="Optionaler Sprecher",
        sprecher_3="Optionaler Sprecher",
        sprecher_4="Optionaler Sprecher",
    )
    async def starten(
        self,
        interaction: discord.Interaction,
        event_id: int | None = None,
        sprecher_1: discord.Member | None = None,
        sprecher_2: discord.Member | None = None,
        sprecher_3: discord.Member | None = None,
        sprecher_4: discord.Member | None = None,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_start")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        speakers = [member for member in (sprecher_1, sprecher_2, sprecher_3, sprecher_4) if member]
        ok, msg = await self.service.start_debate(
            interaction.guild,
            interaction.user,
            event_id=int(event_id) if event_id else None,
            speakers=speakers,
        )
        await _ephemeral(interaction, msg)

    @debatte.command(name="beenden", description="⏹️ 𑁉 Laufende Debatte beenden und archivieren")
    async def beenden(self, interaction: discord.Interaction):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "debate_end")
        if err:
            return await _ephemeral(interaction, err)
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.service.end_debate(interaction.guild, interaction.user)
        await _ephemeral(interaction, msg)
