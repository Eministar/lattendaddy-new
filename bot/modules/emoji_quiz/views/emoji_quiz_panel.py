from __future__ import annotations

import discord

from bot.modules.emoji_quiz.data.question_bank import EMOJI_QUIZ_BANK, EMOJI_QUIZ_CATEGORY_ORDER
from bot.modules.emoji_quiz.formatting.emoji_quiz_embeds import (
    build_leaderboard_embed,
    build_notice_embed,
    build_streaks_embed,
)


async def _send_ephemeral(interaction: discord.Interaction, content: str | None = None, embed: discord.Embed | None = None):
    if embed is None and content is not None:
        settings = getattr(interaction.client, "settings", None)
        if settings:
            embed = build_notice_embed(settings, interaction.guild, content)
            content = None
        else:
            embed = discord.Embed(title="ℹ️ 𑁉 EMOJI-QUIZ", description=content, color=0xB16B91)
            content = None
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=content, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(content=content, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class EmojiQuizCategorySelect(discord.ui.Select):
    def __init__(self, category_options: list[discord.SelectOption] | None = None, disabled: bool = False):
        options = category_options or []
        if not options:
            for key in EMOJI_QUIZ_CATEGORY_ORDER:
                payload = EMOJI_QUIZ_BANK[key]
                options.append(
                    discord.SelectOption(
                        label=str(payload["label"]),
                        value=str(key),
                        emoji=str(payload["emoji"]),
                        description=f"{len(payload['items'])} Rätsel",
                    )
                )
        super().__init__(
            placeholder="Kategorie wählen und Runde starten ...",
            custom_id="starry:emoji_quiz:category",
            options=options[:25],
            min_values=1,
            max_values=1,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        service = getattr(interaction.client, "emoji_quiz_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Emoji-Quiz-Service nicht verfügbar.")
        await interaction.response.defer()
        ok, msg = await service.panel_start_category(interaction, str(self.values[0]))
        if ok:
            return
        return await _send_ephemeral(interaction, msg)


class EmojiQuizButton(discord.ui.Button):
    def __init__(self, action: str):
        labels = {
            "random": ("Zufall", "🎲", discord.ButtonStyle.success),
            "leaderboard_weekly": ("Woche", "🏆", discord.ButtonStyle.secondary),
            "leaderboard_monthly": ("Monat", "🥇", discord.ButtonStyle.secondary),
            "streaks": ("Streaks", "🔥", discord.ButtonStyle.secondary),
            "stats": ("Stats", "📊", discord.ButtonStyle.secondary),
            "submit_question": ("Frage", "📥", discord.ButtonStyle.primary),
            "submit_user": ("User", "👤", discord.ButtonStyle.secondary),
        }
        label, emoji, style = labels.get(action, ("Aktion", "🧩", discord.ButtonStyle.secondary))
        super().__init__(label=label, emoji=emoji, style=style, custom_id=f"starry:emoji_quiz:{action}")

    async def callback(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.user:
            return await _send_ephemeral(interaction, "Nur im Server nutzbar.")
        service = getattr(interaction.client, "emoji_quiz_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Emoji-Quiz-Service nicht verfügbar.")
        action = str(self.custom_id).split(":")[-1]
        if action == "random":
            await interaction.response.defer()
            ok, msg = await service.panel_start_random(interaction)
            if ok:
                return
            return await _send_ephemeral(interaction, msg)
        if action == "leaderboard_weekly":
            week_key, _ = service.current_period_keys()
            rows = await interaction.client.db.list_emoji_quiz_players_top_weekly(interaction.guild.id, week_key, limit=10)
            emb = build_leaderboard_embed(interaction.client.settings, interaction.guild, rows, title="🏆 𑁉 EMOJI-WOCHE")
            return await _send_ephemeral(interaction, embed=emb)
        if action == "leaderboard_monthly":
            _, month_key = service.current_period_keys()
            rows = await interaction.client.db.list_emoji_quiz_players_top_monthly(interaction.guild.id, month_key, limit=10)
            emb = build_leaderboard_embed(interaction.client.settings, interaction.guild, rows, title="🥇 𑁉 EMOJI-MONAT")
            return await _send_ephemeral(interaction, embed=emb)
        if action == "streaks":
            rows = await interaction.client.db.list_emoji_quiz_players_top_streak(interaction.guild.id, limit=10)
            emb = build_streaks_embed(interaction.client.settings, interaction.guild, rows)
            return await _send_ephemeral(interaction, embed=emb)
        if action == "stats":
            emb = await service.stats_summary_embed(interaction.guild.id, int(interaction.user.id), interaction.guild)
            return await _send_ephemeral(interaction, embed=emb)
        if action == "submit_question":
            return await service.open_question_submit_modal(interaction)
        if action == "submit_user":
            return await service.open_user_submit_modal(interaction)
        return await _send_ephemeral(interaction, "Unbekannte Aktion.")


class EmojiQuizPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(EmojiQuizCategorySelect())
        self.add_item(EmojiQuizButton("random"))
        self.add_item(EmojiQuizButton("leaderboard_weekly"))
        self.add_item(EmojiQuizButton("leaderboard_monthly"))
        self.add_item(EmojiQuizButton("streaks"))
        self.add_item(EmojiQuizButton("stats"))
        self.add_item(EmojiQuizButton("submit_question"))
        self.add_item(EmojiQuizButton("submit_user"))
