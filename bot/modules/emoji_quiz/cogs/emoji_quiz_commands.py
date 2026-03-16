from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.emoji_quiz.formatting.emoji_quiz_embeds import build_leaderboard_embed, build_streaks_embed
from bot.modules.emoji_quiz.services.emoji_quiz_service import EmojiQuizService
from bot.modules.moderation.services.permission_service import PermissionService


async def _ephemeral(interaction: discord.Interaction, text: str | None = None, embed: discord.Embed | None = None):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(text, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class EmojiQuizCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "emoji_quiz_service", None) or EmojiQuizService(bot, bot.settings, bot.db, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    emojiquiz = app_commands.Group(name="emojiquiz", description="🧠 𑁉 Emoji-Quiz")

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

    def _split_categories(self, raw: str | None) -> list[str] | None:
        if raw is None:
            return None
        parts = [str(part).strip() for part in str(raw).split(",")]
        cleaned = [part for part in parts if part]
        return cleaned or None

    def _truncate_choice(self, text: str) -> str:
        return str(text or "")[:100]

    @emojiquiz.command(name="setup", description="⚙️ 𑁉 Ziel-Channel/Thread und Panel setzen")
    @app_commands.describe(
        channel="Textkanal (optional)",
        thread="Thread (optional)",
        review_forum="Forum-Channel für Einsendungen",
        timeout_seconds="Rundenlänge in Sekunden",
        auto_enabled="Auto-Quiz direkt aktivieren",
        auto_interval_seconds="Abstand zwischen Auto-Runden",
        categories="Komma-Liste, z. B. filme,serien,städte,user",
    )
    async def setup(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        thread: discord.Thread | None = None,
        review_forum: discord.ForumChannel | None = None,
        timeout_seconds: int = 240,
        auto_enabled: bool = False,
        auto_interval_seconds: int = 240,
        categories: str | None = None,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "emoji_quiz_setup")
        if err:
            return await _ephemeral(interaction, err)
        target = self._resolve_target(interaction, channel, thread)
        if target is None:
            return await _ephemeral(interaction, "Bitte Textkanal oder Thread angeben.")
        parsed_categories = self._split_categories(categories)
        if categories is not None:
            resolved_categories = await self.service._clean_category_inputs(interaction.guild.id, parsed_categories)
            if not resolved_categories:
                return await _ephemeral(interaction, "Keine gültigen Kategorien erkannt.")
        else:
            resolved_categories = None
        await self.service.setup_target(
            interaction.guild,
            target,
            timeout_seconds=int(timeout_seconds),
            auto_interval_seconds=int(auto_interval_seconds),
            auto_enabled=bool(auto_enabled),
            enabled_categories=resolved_categories,
            review_forum=review_forum,
        )
        review_text = f" Review-Forum: {review_forum.mention}." if review_forum else ""
        await _ephemeral(interaction, f"Emoji-Quiz ist jetzt in {target.mention} eingerichtet.{review_text}")

    @emojiquiz.command(name="panel", description="♻️ 𑁉 Emoji-Panel aktualisieren")
    @app_commands.describe(channel="Optional anderer Textkanal", thread="Optional anderer Thread")
    async def panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        thread: discord.Thread | None = None,
    ):
        if not self._need_member(interaction):
            return
        err = self.permission_service.action_error(interaction.user, "emoji_quiz_panel")
        if err:
            return await _ephemeral(interaction, err)
        target = self._resolve_target(interaction, channel, thread)
        if target is None:
            state = await self.service._guild_state(interaction.guild.id)
            target = await self.service._resolve_target(interaction.guild, int(state["target_channel_id"]), int(state["target_thread_id"]))
        if target is None:
            return await _ephemeral(interaction, "Kein Ziel gesetzt. Nutze zuerst `/emojiquiz setup`.")
        await self.service.ensure_panel(interaction.guild, target)
        await _ephemeral(interaction, f"Emoji-Panel in {target.mention} aktualisiert.")

    @emojiquiz.command(name="start", description="🎯 𑁉 Emoji-Rätsel starten")
    @app_commands.describe(category="Optionale Kategorie")
    async def start(self, interaction: discord.Interaction, category: str | None = None):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "emoji_quiz_start"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        target = self._resolve_target(interaction, None, None)
        ok, msg = await self.service.start_round(
            interaction.guild,
            actor=interaction.user,
            category_key=category,
            target_override=target,
        )
        await _ephemeral(interaction, msg)

    @start.autocomplete("category")
    async def start_category_autocomplete(self, interaction: discord.Interaction, current: str):
        if not interaction.guild:
            return []
        return [
            app_commands.Choice(name=self._truncate_choice(label), value=value)
            for value, label in await self.service.autocomplete_category_choices(interaction.guild.id, current, enabled_only=True)
        ]

    @emojiquiz.command(name="stop", description="⏹️ 𑁉 Laufendes Emoji-Rätsel beenden")
    @app_commands.describe(reason="Optionaler Grund")
    async def stop(self, interaction: discord.Interaction, reason: str | None = None):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "emoji_quiz_stop"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        ok, msg = await self.service.stop_round(interaction.guild, actor=interaction.user, reason=str(reason or "Manuell gestoppt"))
        await _ephemeral(interaction, msg)

    @emojiquiz.command(name="auto", description="🤖 𑁉 Auto-Quiz ein- oder ausschalten")
    @app_commands.describe(enabled="Auto-Quiz aktivieren?", interval_seconds="Abstand zwischen Auto-Runden")
    async def auto(self, interaction: discord.Interaction, enabled: bool, interval_seconds: int | None = None):
        if not self._need_member(interaction):
            return
        if not await self.service.can_manage(interaction.user, "emoji_quiz_auto"):
            return await _ephemeral(interaction, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt.")
        await self.service.set_auto(interaction.guild.id, bool(enabled), interval_seconds=interval_seconds)
        await self.service.refresh_dashboard(interaction.guild)
        await _ephemeral(interaction, f"Auto-Quiz ist jetzt **{'an' if enabled else 'aus'}**.")

    @emojiquiz.command(name="categories", description="🗂️ 𑁉 Aktive Kategorien anzeigen oder setzen")
    @app_commands.describe(setzen="Optional neue Komma-Liste, z. B. filme,serien,städte,user")
    async def categories(self, interaction: discord.Interaction, setzen: str | None = None):
        if not interaction.guild:
            return
        if setzen is not None:
            if not self._need_member(interaction):
                return
            err = self.permission_service.action_error(interaction.user, "emoji_quiz_setup")
            if err:
                return await _ephemeral(interaction, err)
            raw_categories = self._split_categories(setzen)
            if not raw_categories:
                return await _ephemeral(interaction, "Keine gültigen Kategorien erkannt.")
            categories = await self.service._clean_category_inputs(interaction.guild.id, raw_categories)
            if not categories:
                return await _ephemeral(interaction, "Keine gültigen Kategorien erkannt.")
            await self.service.set_categories(interaction.guild.id, categories)
            await self.service.refresh_dashboard(interaction.guild)
        await _ephemeral(interaction, "**Aktive Kategorien**\n" + await self.service.categories_text(interaction.guild.id))

    @emojiquiz.command(name="annehmen", description="✅ 𑁉 Emoji-Quiz-Einreichung annehmen")
    async def accept(self, interaction: discord.Interaction):
        await self.service.set_submission_status(interaction, "accepted")

    @emojiquiz.command(name="ablehnen", description="⛔ 𑁉 Emoji-Quiz-Einreichung ablehnen")
    async def reject(self, interaction: discord.Interaction):
        await self.service.set_submission_status(interaction, "rejected")

    @emojiquiz.command(name="leaderboard", description="🏆 𑁉 Emoji-Leaderboard")
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
            rows = await self.bot.db.list_emoji_quiz_players_top_weekly(interaction.guild.id, week_key, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="🏆 𑁉 EMOJI-WOCHE")
        elif period == "monthly":
            _, month_key = self.service.current_period_keys()
            rows = await self.bot.db.list_emoji_quiz_players_top_monthly(interaction.guild.id, month_key, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="🥇 𑁉 EMOJI-MONAT")
        else:
            rows = await self.bot.db.list_emoji_quiz_players_top_alltime(interaction.guild.id, limit=10)
            embed = build_leaderboard_embed(self.bot.settings, interaction.guild, rows, title="👑 𑁉 EMOJI-ALLTIME")
        await _ephemeral(interaction, embed=embed)

    @emojiquiz.command(name="streaks", description="🔥 𑁉 Emoji-Streaks")
    async def streaks(self, interaction: discord.Interaction):
        if not interaction.guild:
            return
        rows = await self.bot.db.list_emoji_quiz_players_top_streak(interaction.guild.id, limit=10)
        await _ephemeral(interaction, embed=build_streaks_embed(self.bot.settings, interaction.guild, rows))

    @emojiquiz.command(name="stats", description="📊 𑁉 Emoji-Stats eines Users")
    @app_commands.describe(user="Optional anderer User")
    async def stats(self, interaction: discord.Interaction, user: discord.Member | None = None):
        if not interaction.guild or not interaction.user:
            return
        target = user or interaction.user
        await _ephemeral(interaction, await self.service.stats_summary_text(interaction.guild.id, int(target.id), interaction.guild))
