from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.guess_the_number.formatting.guess_number_embeds import (
    build_leaderboard_embed,
    build_streaks_embed,
)
from bot.modules.guess_the_number.services.guess_number_service import GuessNumberService
from bot.modules.moderation.services.permission_service import PermissionService


async def _ephemeral(interaction: discord.Interaction, text: str | None = None, embed: discord.Embed | None = None):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(text, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class GuessNumberCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "guess_number_service", None) or GuessNumberService(bot, bot.settings, bot.db, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    guess = app_commands.Group(name="guess", description="🎲 𑁉 Guess-The-Number")

    def _need_member(self, interaction: discord.Interaction) -> bool:
        return bool(interaction.guild and isinstance(interaction.user, discord.Member))

    def _resolve_target(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None,
        thread: discord.Thread | None,
    ) -> discord.TextChannel | discord.Thread | None:
        if thread:
            return thread
        if channel:
            return channel
        if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            return interaction.channel
        return None

    @guess.command(name="setup", description="⚙️ 𑁉 Ziel-Channel/Thread setzen und Panel senden")
    @app_commands.describe(
        channel="Textkanal (optional)",
        thread="Thread (optional)",
        minimum="Standard-Minimum",
        maximum="Standard-Maximum",
        timeout_seconds="Rundenlänge in Sekunden",
        auto_enabled="Auto-Event direkt aktivieren",
        auto_interval_seconds="Abstand zwischen Auto-Runden",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        thread: discord.Thread | None = None,
        minimum: int = 1,
        maximum: int = 100,
        timeout_seconds: int = 180,
        auto_enabled: bool = False,
        auto_interval_seconds: int = 180,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "guess_setup")
        if err:
            return await _ephemeral(interaction, err)
        if int(minimum) == int(maximum):
            return await _ephemeral(interaction, "Min und Max dürfen nicht identisch sein.")
        target = self._resolve_target(interaction, channel, thread)
        if target is None:
            return await _ephemeral(interaction, "Bitte Textkanal oder Thread angeben.")
        await self.service.setup_target(
            interaction.guild,
            target,
            default_min=int(minimum),
            default_max=int(maximum),
            timeout_seconds=int(timeout_seconds),
            auto_interval_seconds=int(auto_interval_seconds),
            auto_enabled=bool(auto_enabled),
        )
        await _ephemeral(interaction, f"Guess-The-Number ist jetzt in {target.mention} eingerichtet.")

    @guess.command(name="panel", description="♻️ 𑁉 Guess-Panel aktualisieren")
    @app_commands.describe(channel="Optional anderer Textkanal", thread="Optional anderer Thread")
    async def panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        thread: discord.Thread | None = None,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "guess_panel")
        if err:
            return await _ephemeral(interaction, err)
        target = self._resolve_target(interaction, channel, thread)
        if target is None:
            state = await self.service._guild_state(interaction.guild.id)
            target = await self.service._resolve_target(interaction.guild, int(state["target_channel_id"]), int(state["target_thread_id"]))
        if target is None:
            return await _ephemeral(interaction, "Kein Ziel gesetzt. Nutze zuerst `/guess setup`.")
        await self.service.ensure_panel(interaction.guild, target)
        await _ephemeral(interaction, f"Guess-Panel in {target.mention} aktualisiert.")

    @guess.command(name="start", description="🎯 𑁉 Neue Guess-Runde starten")
    @app_commands.describe(minimum="Optional anderes Minimum", maximum="Optional anderes Maximum")
    async def start(
        self,
        interaction: discord.Interaction,
        minimum: int | None = None,
        maximum: int | None = None,
    ):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "guess_start"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        target = self._resolve_target(interaction, None, None)
        ok, msg = await self.service.start_round(
            interaction.guild,
            actor=interaction.user,
            min_number=minimum,
            max_number=maximum,
            target_override=target,
        )
        await _ephemeral(interaction, msg)

    @guess.command(name="stop", description="⏹️ 𑁉 Laufende Guess-Runde beenden")
    @app_commands.describe(reason="Optionaler Grund")
    async def stop(self, interaction: discord.Interaction, reason: str | None = None):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "guess_stop"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        ok, msg = await self.service.stop_round(interaction.guild, actor=interaction.user, reason=str(reason or "Manuell gestoppt"))
        await _ephemeral(interaction, msg)

    @guess.command(name="range", description="🔢 𑁉 Standard-Range ändern")
    async def change_range(self, interaction: discord.Interaction, minimum: int, maximum: int):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "guess_setup")
        if err:
            return await _ephemeral(interaction, err)
        if int(minimum) == int(maximum):
            return await _ephemeral(interaction, "Min und Max dürfen nicht identisch sein.")
        await self.service.set_default_range(interaction.guild.id, int(minimum), int(maximum))
        await self.service.refresh_dashboard(interaction.guild)
        await _ephemeral(interaction, f"Neue Default-Range: **{int(minimum)}** bis **{int(maximum)}**")

    @guess.command(name="auto", description="🤖 𑁉 Auto-Event ein- oder ausschalten")
    @app_commands.describe(enabled="Auto-Event aktivieren?", interval_seconds="Abstand zwischen Auto-Runden")
    async def auto(self, interaction: discord.Interaction, enabled: bool, interval_seconds: int | None = None):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "guess_auto"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        await self.service.set_auto(interaction.guild.id, bool(enabled), interval_seconds=interval_seconds)
        await self.service.refresh_dashboard(interaction.guild)
        await _ephemeral(interaction, f"Auto-Event ist jetzt **{'an' if enabled else 'aus'}**.")

    @guess.command(name="leaderboard", description="🏆 𑁉 Guess-Leaderboard")
    @app_commands.describe(zeitraum="alltime / weekly / monthly")
    @app_commands.choices(zeitraum=[
        app_commands.Choice(name="alltime", value="alltime"),
        app_commands.Choice(name="weekly", value="weekly"),
        app_commands.Choice(name="monthly", value="monthly"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, zeitraum: app_commands.Choice[str] | None = None):
        if not interaction.guild:
            return
        period = str(zeitraum.value if zeitraum else "alltime").lower()
        if period == "weekly":
            week_key, _ = self.service.current_period_keys()
            rows = await self.bot.db.list_guess_number_players_top_weekly(interaction.guild.id, week_key, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="🏆 𑁉 GUESS-WOCHE")
        elif period == "monthly":
            _, month_key = self.service.current_period_keys()
            rows = await self.bot.db.list_guess_number_players_top_monthly(interaction.guild.id, month_key, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="🥇 𑁉 GUESS-MONAT")
        else:
            rows = await self.bot.db.list_guess_number_players_top_alltime(interaction.guild.id, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="👑 𑁉 GUESS-ALLTIME")
        await _ephemeral(interaction, embed=embed)

    @guess.command(name="streaks", description="🔥 𑁉 Guess-Streaks")
    async def streaks(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        rows = await self.bot.db.list_guess_number_players_top_streak(interaction.guild.id, limit=10)
        await _ephemeral(interaction, embed=build_streaks_embed(self.bot.settings, interaction.guild, rows))

    @guess.command(name="stats", description="📊 𑁉 Guess-Stats eines Users")
    @app_commands.describe(user="Optional anderer User")
    async def stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if not interaction.guild or not interaction.user:
            return
        target = user or interaction.user
        text = await self.service.stats_summary_text(interaction.guild.id, int(target.id), interaction.guild)
        await _ephemeral(interaction, text)
