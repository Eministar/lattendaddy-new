from __future__ import annotations

import discord

from bot.modules.guess_the_number.formatting.guess_number_embeds import (
    build_leaderboard_embed,
    build_streaks_embed,
)


async def _send_ephemeral(interaction: discord.Interaction, content: str | None = None, embed: discord.Embed | None = None):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(content=content, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class GuessDashboardButton(discord.ui.Button):
    def __init__(self, action: str):
        labels = {
            "start": ("Start", "🎲", discord.ButtonStyle.success),
            "leaderboard_weekly": ("Woche", "🏆", discord.ButtonStyle.secondary),
            "leaderboard_monthly": ("Monat", "🥇", discord.ButtonStyle.secondary),
            "streaks": ("Streaks", "🔥", discord.ButtonStyle.secondary),
            "stats": ("Stats", "📊", discord.ButtonStyle.secondary),
        }
        label, emoji, style = labels.get(action, ("Aktion", "🧩", discord.ButtonStyle.secondary))
        super().__init__(label=label, emoji=emoji, style=style, custom_id=f"starry:guess_dash:{action}")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.user:
            return await _send_ephemeral(interaction, "Nur im Server nutzbar.")
        service = getattr(interaction.client, "guess_number_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Guess-Service nicht verfügbar.")
        action = str(self.custom_id).split(":")[-1]
        if action == "start":
            ok, msg = await service.panel_start(interaction)
            return await _send_ephemeral(interaction, msg if not ok else "Runde gestartet.")
        if action == "leaderboard_weekly":
            week_key, _ = service.current_period_keys()
            rows = await interaction.client.db.list_guess_number_players_top_weekly(interaction.guild.id, week_key, limit=10)
            emb = build_leaderboard_embed(interaction.client.settings, interaction.guild, rows, title="🏆 𑁉 GUESS-WOCHE")
            return await _send_ephemeral(interaction, embed=emb)
        if action == "leaderboard_monthly":
            _, month_key = service.current_period_keys()
            rows = await interaction.client.db.list_guess_number_players_top_monthly(interaction.guild.id, month_key, limit=10)
            emb = build_leaderboard_embed(interaction.client.settings, interaction.guild, rows, title="🥇 𑁉 GUESS-MONAT")
            return await _send_ephemeral(interaction, embed=emb)
        if action == "streaks":
            rows = await interaction.client.db.list_guess_number_players_top_streak(interaction.guild.id, limit=10)
            emb = build_streaks_embed(interaction.client.settings, interaction.guild, rows)
            return await _send_ephemeral(interaction, embed=emb)
        if action == "stats":
            text = await service.stats_summary_text(interaction.guild.id, int(interaction.user.id), interaction.guild)
            return await _send_ephemeral(interaction, text)
        return await _send_ephemeral(interaction, "Unbekannte Aktion.")


class GuessNumberPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GuessDashboardButton("start"))
        self.add_item(GuessDashboardButton("leaderboard_weekly"))
        self.add_item(GuessDashboardButton("leaderboard_monthly"))
        self.add_item(GuessDashboardButton("streaks"))
        self.add_item(GuessDashboardButton("stats"))
