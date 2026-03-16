from __future__ import annotations

from datetime import datetime

import discord
from discord.utils import format_dt

from bot.utils.assets import Banners
from bot.utils.emojis import em


def _color(settings, guild: discord.Guild | None) -> int:
    gid = guild.id if guild else 0
    raw = str(settings.get_guild(gid, "design.accent_color", "#B16B91") or "").replace("#", "").strip()
    try:
        return int(raw, 16)
    except Exception:
        return 0xB16B91


def _add_banner(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=Banners.COUNTING)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def build_dashboard_view(settings, guild: discord.Guild | None, stats: dict, buttons: list[discord.ui.Button]) -> discord.ui.LayoutView:
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"
    header = f"**{info} 𑁉 GUESS THE NUMBER**"
    desc = (
        f"{arrow2} Starte ein gemeinsames Zahlen-Event direkt im aktuellen Channel oder Thread.\n"
        f"{arrow2} Wer die Zahl zuerst trifft, gewinnt die Runde und klettert im Leaderboard.\n"
        f"{arrow2} Eine Runde bleibt schlicht: starten, raten, gewinnen.\n\n"
        f"┏`📍` - Ziel: {stats.get('target', 'Nicht gesetzt')}\n"
        f"┣`🎯` - Default-Range: **{int(stats.get('default_min', 1))}** bis **{int(stats.get('default_max', 100))}**\n"
        f"┣`👥` - Spieler: **{int(stats.get('players', 0))}**\n"
        f"┣`🎮` - Runden: **{int(stats.get('rounds', 0))}**\n"
        f"┣`👑` - Champion: {stats.get('champion', 'Noch kein Champion')}\n"
        f"┗`🧵` - Aktiv: {stats.get('active_state', 'Keine Runde aktiv')}"
    )
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    container.add_item(discord.ui.Separator())
    for i in range(0, len(buttons), 5):
        row = discord.ui.ActionRow()
        for button in buttons[i:i + 5]:
            row.add_item(button)
        container.add_item(row)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def build_round_embed(
    settings,
    guild: discord.Guild | None,
    started_by: int | None,
    min_number: int,
    max_number: int,
    end_at: datetime,
    round_number: int,
    auto_started: bool = False,
) -> discord.Embed:
    arrow2 = em(settings, "arrow2", guild) or "»"
    timer = f"{format_dt(end_at, style='R')} ({format_dt(end_at, style='t')})"
    desc = (
        f"{arrow2} Sende eine ganze Zahl im Ziel-Channel, um mitzuraten.\n\n"
        f"┏`🎮` - Runde: **#{int(round_number)}**\n"
        f"┣`🔢` - Bereich: **{int(min_number)}** bis **{int(max_number)}**\n"
        f"┣`🧠` - Tipps: **Zu hoch / Zu niedrig**\n"
        f"┣`👤` - Gestartet von: {f'<@{int(started_by)}>' if started_by else 'System'}\n"
        f"┗`⏱️` - Ende: {timer}"
    )
    return discord.Embed(
        title="🎲 𑁉 ZAHLENSUCHE GESTARTET",
        description=desc,
        color=_color(settings, guild),
    )


def build_result_embed(
    settings,
    guild: discord.Guild | None,
    winner_id: int,
    number: int,
    guesses: int,
    total_wins: int,
    streak: int,
) -> discord.Embed:
    desc = (
        f"┏`👑` - Gewinner: <@{int(winner_id)}>\n"
        f"┣`🔢` - Zahl: **{int(number)}**\n"
        f"┣`💬` - Versuche: **{int(guesses)}**\n"
        f"┣`🏆` - Siege gesamt: **{int(total_wins)}**\n"
        f"┗`🔥` - Streak: **{int(streak)}**"
    )
    return discord.Embed(
        title="✅ 𑁉 TREFFER!",
        description=desc,
        color=_color(settings, guild),
    )


def build_closed_embed(
    settings,
    guild: discord.Guild | None,
    number: int,
    guesses: int,
    reason: str,
) -> discord.Embed:
    desc = (
        f"┏`🔢` - Zahl: **{int(number)}**\n"
        f"┣`💬` - Versuche: **{int(guesses)}**\n"
        f"┗`📌` - Grund: **{reason}**"
    )
    return discord.Embed(
        title="⏹️ 𑁉 RUNDE GESCHLOSSEN",
        description=desc,
        color=_color(settings, guild),
    )


def build_leaderboard_embed(settings, guild: discord.Guild, rows: list[tuple], title: str) -> discord.Embed:
    if not rows:
        return discord.Embed(title=title, description="Noch keine Einträge.", color=_color(settings, guild))
    lines: list[str] = []
    for idx, row in enumerate(rows, 1):
        user_id = int(row[0])
        wins = int(row[1] or 0)
        guesses = int(row[2] or 0)
        member = guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        lines.append(f"`#{idx}` **{name}** — **{wins}** Siege • {guesses} Tipps")
    return discord.Embed(title=title, description="\n".join(lines), color=_color(settings, guild))


def build_streaks_embed(settings, guild: discord.Guild, rows: list[tuple]) -> discord.Embed:
    if not rows:
        return discord.Embed(title="🔥 𑁉 STREAKS", description="Noch keine Einträge.", color=_color(settings, guild))
    lines: list[str] = []
    for idx, row in enumerate(rows, 1):
        user_id = int(row[0])
        current_streak = int(row[1] or 0)
        best_streak = int(row[2] or 0)
        member = guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        lines.append(f"`#{idx}` **{name}** — Streak **{current_streak}** (Best **{best_streak}**)")
    return discord.Embed(
        title="🔥 𑁉 GUESS-STREAKS",
        description="\n".join(lines),
        color=_color(settings, guild),
    )
