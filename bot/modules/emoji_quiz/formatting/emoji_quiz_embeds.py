from __future__ import annotations

from datetime import datetime, timezone

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
        gallery.add_item(media=Banners.FLAGS)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def build_dashboard_view(
    settings,
    guild: discord.Guild | None,
    stats: dict,
    category_select: discord.ui.Select,
    buttons: list[discord.ui.Button],
) -> discord.ui.LayoutView:
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"
    header = f"**{info} 𑁉 EMOJI QUIZ**"
    desc = (
        f"{arrow2} Wähle eine Kategorie im Dropdown oder starte eine Zufallsrunde.\n"
        f"{arrow2} Die erste richtige Antwort gewinnt Punkte, Streak und Platz im Leaderboard.\n"
        f"{arrow2} Antworten werden geprüft und nach kurzer Zeit wieder aus dem Channel entfernt.\n\n"
        f"┏`📍` - Ziel: {stats.get('target', 'Nicht gesetzt')}\n"
        f"┣`🧩` - Kategorien: **{int(stats.get('categories', 0))}** aktiv\n"
        f"┣`👥` - Spieler: **{int(stats.get('players', 0))}**\n"
        f"┣`🎮` - Runden: **{int(stats.get('rounds', 0))}**\n"
        f"┣`👑` - Champion: {stats.get('champion', 'Noch kein Champion')}\n"
        f"┣`📥` - Community: Eigene Rätsel und User-Profile einreichen\n"
        f"┗`🧵` - Aktiv: {stats.get('active_state', 'Keine Runde aktiv')}"
    )
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    container.add_item(discord.ui.Separator())
    select_row = discord.ui.ActionRow()
    select_row.add_item(category_select)
    container.add_item(select_row)
    for idx in range(0, len(buttons), 5):
        row = discord.ui.ActionRow()
        for button in buttons[idx:idx + 5]:
            row.add_item(button)
        container.add_item(row)
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def build_round_embed(
    settings,
    guild: discord.Guild | None,
    category_label: str,
    prompt: str,
    end_at: datetime,
    round_number: int,
    started_by: int | None = None,
    auto_started: bool = False,
    hints_enabled: bool = False,
) -> discord.Embed:
    mode = "Auto-Quiz" if auto_started else "Manuell"
    hint_text = "Aktiv" if hints_enabled else "Aus"
    desc = (
        f"## {prompt}\n\n"
        f"┏`🎮` - Runde: **#{int(round_number)}**\n"
        f"┣`🗂️` - Kategorie: **{category_label}**\n"
        f"┣`⚙️` - Modus: **{mode}**\n"
        f"┣`👤` - Gestartet von: {f'<@{int(started_by)}>' if started_by else 'System'}\n"
        f"┣`💡` - Hinweise: **{hint_text}**\n"
        f"┗`⏱️` - Ende: {format_dt(end_at, style='R')} ({format_dt(end_at, style='t')})"
    )
    return discord.Embed(
        title="🧠 𑁉 EMOJI-RÄTSEL",
        description=desc,
        color=_color(settings, guild),
    )


def build_result_embed(
    settings,
    guild: discord.Guild | None,
    winner_id: int,
    answer: str,
    category_label: str,
    points: int,
    total_points: int,
    streak: int,
) -> discord.Embed:
    desc = (
        f"┏`👑` - Gewinner: <@{int(winner_id)}>\n"
        f"┣`🗂️` - Kategorie: **{category_label}**\n"
        f"┣`✅` - Lösung: **{answer}**\n"
        f"┣`💎` - Punkte: **+{int(points)}** (Gesamt: **{int(total_points)}**)\n"
        f"┗`🔥` - Streak: **{int(streak)}**"
    )
    return discord.Embed(
        title="✅ 𑁉 RICHTIG!",
        description=desc,
        color=_color(settings, guild),
    )


def build_closed_embed(
    settings,
    guild: discord.Guild | None,
    answer: str,
    category_label: str,
    reason: str,
) -> discord.Embed:
    desc = (
        f"┏`🗂️` - Kategorie: **{category_label}**\n"
        f"┣`✅` - Lösung: **{answer}**\n"
        f"┗`📌` - Grund: **{reason}**"
    )
    return discord.Embed(
        title="⏹️ 𑁉 QUIZ GESCHLOSSEN",
        description=desc,
        color=_color(settings, guild),
    )


def build_leaderboard_embed(settings, guild: discord.Guild, rows: list[tuple], title: str) -> discord.Embed:
    if not rows:
        return discord.Embed(title=title, description="Noch keine Einträge.", color=_color(settings, guild))
    lines: list[str] = []
    for idx, row in enumerate(rows, 1):
        user_id = int(row[0])
        points = int(row[1] or 0)
        correct = int(row[2] or 0)
        member = guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        lines.append(f"`#{idx}` **{name}** — **{points}** Punkte • {correct} Treffer")
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
    return discord.Embed(title="🔥 𑁉 EMOJI-STREAKS", description="\n".join(lines), color=_color(settings, guild))


def _fmt_dt(value: str | None) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return str(value)
    return format_dt(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))


def build_submission_view(settings, guild: discord.Guild | None, data: dict) -> discord.ui.LayoutView:
    submission_type = str(data.get("submission_type") or "question")
    status = str(data.get("status") or "pending")
    type_label = {
        "question": "Frage",
        "user_question": "User-Frage",
        "category": "Kategorie",
    }.get(submission_type, "Einreichung")
    status_label = {
        "accepted": "✅ ANGENOMMEN",
        "rejected": "⛔ ABGELEHNT",
        "pending": "⏳ ERWARTET",
    }.get(status, "⏳ ERWARTET")
    user_id = int(data.get("user_id") or 0)
    subject_user_id = int(data.get("subject_user_id") or 0)
    category_label = str(data.get("category_label") or data.get("category_key") or "—")
    prompt = str(data.get("prompt") or "—").strip()
    answer = str(data.get("answer") or "—").strip()
    aliases = [str(alias).strip() for alias in list(data.get("aliases") or []) if str(alias).strip()]
    created_at = _fmt_dt(data.get("created_at"))
    decided_at = _fmt_dt(data.get("decided_at"))
    decided_by = int(data.get("decided_by") or 0)

    meta_lines = [
        f"┏`👤` - Von: <@{user_id}>",
        f"┣`📦` - Typ: **{type_label}**",
        f"┣`🗂️` - Kategorie: **{category_label}**",
        f"┣`⏰` - Eingereicht: {created_at}",
        f"┗`📌` - Status: **{status_label}**",
    ]
    content_lines = [f"## {prompt}"]
    if submission_type == "category":
        content_lines.append(f"**Beschreibung**\n{answer or '—'}")
    else:
        content_lines.append(f"**Lösung**\n{answer or '—'}")
        if aliases:
            content_lines.append(f"**Aliase**\n{', '.join(aliases[:10])}")
    if subject_user_id:
        content_lines.append(f"**Bezieht sich auf**\n<@{subject_user_id}>")

    review_lines = []
    if status in {"accepted", "rejected"}:
        review_lines.append(f"┏`🧑‍⚖️` - Geprüft von: {f'<@{decided_by}>' if decided_by else '—'}")
        review_lines.append(f"┗`🗓️` - Entscheidung: {decided_at}")
    else:
        review_lines.append("┗`🔎` - Prüfung: ausstehend")

    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"**📥 𑁉 EMOJI-QUIZ-EINREICHUNG**\n" + "\n".join(meta_lines)))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("\n\n".join(content_lines)))
    view.add_item(container)

    status_container = discord.ui.Container(accent_colour=_color(settings, guild))
    status_container.add_item(discord.ui.TextDisplay("**REVIEW**"))
    status_container.add_item(discord.ui.Separator())
    status_container.add_item(discord.ui.TextDisplay("\n".join(review_lines)))
    view.add_item(status_container)
    return view
