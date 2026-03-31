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


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fmt_dt(value: str | None, style: str = "f") -> str:
    dt = _parse_dt(value)
    if not dt:
        return "—"
    return format_dt(dt, style=style)


def _fmt_duration(total_seconds: int | None) -> str:
    seconds = max(0, int(total_seconds or 0))
    if seconds <= 0:
        return "—"
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not hours:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


def _truncate(text: str, limit: int) -> str:
    clean = str(text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"


def _speaker_lines(snapshot: list[dict] | None) -> str:
    rows = list(snapshot or [])
    if not rows:
        return "Noch keine Sprecher hinterlegt."
    lines: list[str] = []
    for item in rows[:8]:
        user_id = int(item.get("user_id") or 0)
        name = str(item.get("name") or f"User {user_id}").strip()
        if user_id:
            lines.append(f"• <@{user_id}> ({name})")
        else:
            lines.append(f"• {name}")
    if len(rows) > 8:
        lines.append(f"• +{len(rows) - 8} weitere")
    return "\n".join(lines)


def build_notice_embed(
    settings,
    guild: discord.Guild | None,
    text: str,
    *,
    title: str = "ℹ️ 𑁉 BKT-DEBATTEN",
) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=str(text or "").strip() or "—",
        color=_color(settings, guild),
    )


def _add_panel_banner(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=Banners.DEBATE)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def build_panel_container(
    settings,
    guild: discord.Guild | None,
    state: dict,
    signup_button: discord.ui.Button,
    topic_button: discord.ui.Button,
    archive_select: discord.ui.Select,
) -> discord.ui.Container:
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"
    sparkles = em(settings, "sparkles", guild) or "✨"
    next_event = state.get("next_event") or {}
    live_event = state.get("live_event") or {}
    next_value = "┗`🗓️` - Aktuell ist noch keine Debatte geplant."
    if next_event:
        next_value = (
            f"┏`🧠` - Thema: **{next_event.get('topic_title', 'Unbekanntes Thema')}**\n"
            f"┣`🗓️` - Termin: {_fmt_dt(next_event.get('scheduled_for'), 'F')} ({_fmt_dt(next_event.get('scheduled_for'), 'R')})\n"
            f"┣`🎤` - Bestätigte Sprecher: **{int(state.get('next_registration_count', 0) or 0)}**\n"
            f"┣`📥` - Offene Anmeldungen: **{int(state.get('next_pending_signup_count', 0) or 0)}**\n"
            f"┗`👥` - Vorschau: {state.get('next_registration_preview', 'Noch keine Sprecher bestätigt.')}"
        )

    live_value = "┗`📡` - Derzeit läuft keine Debatte."
    if live_event:
        live_value = (
            f"┏`🧠` - Thema: **{live_event.get('topic_title', 'Unbekanntes Thema')}**\n"
            f"┣`⏱️` - Start: {_fmt_dt(live_event.get('started_at'), 'F')} ({_fmt_dt(live_event.get('started_at'), 'R')})\n"
            f"┣`🎤` - Sprecher: **{int(state.get('live_speaker_count', 0) or 0)}**\n"
            f"┣`🎙️` - Stage: {state.get('live_stage_mention', 'Nicht gesetzt')}\n"
            f"┗`💬` - Podium: {state.get('podium_mention', 'Nicht gesetzt')}"
        )

    archive_value = (
        f"┏`📥` - Offene Themen: **{int(state.get('pending_topic_count', 0) or 0)}**\n"
        f"┣`✅` - Bestätigte Themen: **{int(state.get('approved_topic_count', 0) or 0)}**\n"
        f"┣`🗂️` - Archivierte Debatten: **{int(state.get('finished_event_count', 0) or 0)}**\n"
        f"┗`📚` - Archiv: Vergangene Debatten unten im Dropdown"
    )
    header = f"**{info} 𑁉 BKT-DEBATTEN**"
    intro = (
        f"{arrow2} Melde dich für die nächste Debatte an oder reiche ein neues Thema ein.\n"
        f"{arrow2} Angenommene Sprecher werden beim Start automatisch für die Stage freigeschaltet."
    )
    cta = f"{sparkles} **Debatte mitgestalten** über Anmeldung, Themeneinsendung und Archiv unten."

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_panel_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}\n\n{cta}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Nächste Debatte**\n{next_value}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Live-Status**\n{live_value}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Themen & Archiv**\n{archive_value}"))
    container.add_item(discord.ui.Separator())
    button_row = discord.ui.ActionRow()
    button_row.add_item(signup_button)
    button_row.add_item(topic_button)
    container.add_item(button_row)
    archive_row = discord.ui.ActionRow()
    archive_row.add_item(archive_select)
    container.add_item(archive_row)
    return container


def build_signup_review_embed(settings, guild: discord.Guild | None, payload: dict) -> discord.Embed:
    arrow2 = em(settings, "arrow2", guild) or "»"
    action = "angemeldet" if payload.get("joined") else "abgemeldet"
    status_label = str(payload.get("status_label") or ("Offen" if payload.get("joined") else "Entfernt"))
    embed = discord.Embed(
        title="🗳️ 𑁉 DEBATTEN-ANMELDUNG",
        description=(
            f"{arrow2} **{payload.get('display_name', 'User')}** hat sich **{action}**.\n\n"
            f"┏`👤` - User: <@{int(payload.get('user_id') or 0)}>\n"
            f"┣`🧠` - Debatte: **{payload.get('topic_title', 'Unbekannt')}**\n"
            f"┣`🗓️` - Termin: {_fmt_dt(payload.get('scheduled_for'), 'F')}\n"
            f"┣`🆔` - Event-ID: **#{int(payload.get('event_id') or 0)}**\n"
            f"┗`📌` - Status: **{status_label}**"
        ),
        color=_color(settings, guild),
    )
    note = str(payload.get("review_note") or "").strip()
    if note:
        embed.add_field(name="Notiz", value=note, inline=False)
    reviewed_by = int(payload.get("reviewed_by") or 0)
    if reviewed_by:
        embed.set_footer(text=f"Bearbeitet von {reviewed_by}")
    return embed


def build_topic_review_embed(settings, guild: discord.Guild | None, payload: dict) -> discord.Embed:
    arrow2 = em(settings, "arrow2", guild) or "»"
    embed = discord.Embed(
        title="🧠 𑁉 DEBATTEN-THEMA",
        description=(
            f"{arrow2} Neues oder geprüftes Debattenthema.\n\n"
            f"**{payload.get('title', 'Ohne Titel')}**\n\n"
            f"{payload.get('description', '—')}"
        ),
        color=_color(settings, guild),
    )
    embed.add_field(
        name="Details",
        value=(
            f"┏`🆔` - Themen-ID: **#{int(payload.get('topic_id') or 0)}**\n"
            f"┣`📌` - Status: **{payload.get('status_label', 'Offen')}**\n"
            f"┣`👤` - Eingereicht von: <@{int(payload.get('user_id') or 0)}>\n"
            f"┗`📦` - Quelle: **{payload.get('source_label', 'Panel')}**"
        ),
        inline=False,
    )
    note = str(payload.get("review_note") or "").strip()
    if note:
        embed.add_field(name="Notiz", value=note, inline=False)
    return embed


def build_podium_embed(settings, guild: discord.Guild | None, event: dict, *, live: bool) -> discord.Embed:
    arrow2 = em(settings, "arrow2", guild) or "»"
    title = "🎙️ 𑁉 BKT-DEBATTE LIVE" if live else "🗂️ 𑁉 BKT-DEBATTE BEENDET"
    stage_channel_id = int(event.get("stage_channel_id") or 0)
    stage_mention = f"<#{stage_channel_id}>" if stage_channel_id else "Nicht aktiv"
    status_line = (
        f"• Start: {_fmt_dt(event.get('started_at'), 'F')} ({_fmt_dt(event.get('started_at'), 'R')})"
        if live
        else (
            f"• Start: {_fmt_dt(event.get('started_at'), 'F')}\n"
            f"• Ende: {_fmt_dt(event.get('ended_at'), 'F')}\n"
            f"• Dauer: **{_fmt_duration(event.get('duration_seconds'))}**"
        )
    )
    embed = discord.Embed(
        title=title,
        description=(
            f"{arrow2} {'Die Debatte läuft jetzt live auf der Stage.' if live else 'Die Debatte wurde beendet und archiviert.'}\n\n"
            f"**{event.get('topic_title', 'Unbekanntes Thema')}**\n\n"
            f"{event.get('topic_description', '—')}"
        ),
        color=_color(settings, guild),
    )
    embed.add_field(
        name="Ablauf",
        value=(
            f"• Geplant für: {_fmt_dt(event.get('scheduled_for'), 'F')}\n"
            f"{status_line}\n"
            f"• Stage: {stage_mention}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Sprecher",
        value=_speaker_lines(event.get("speaker_snapshot")),
        inline=False,
    )
    return embed


def build_archive_embed(settings, guild: discord.Guild | None, event: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"🗂️ 𑁉 DEBATTEN-ARCHIV #{int(event.get('id') or 0)}",
        description=(
            f"**{event.get('topic_title', 'Unbekanntes Thema')}**\n\n"
            f"{event.get('topic_description', '—')}"
        ),
        color=_color(settings, guild),
    )
    embed.add_field(
        name="Zeitplan",
        value=(
            f"• Geplant für: {_fmt_dt(event.get('scheduled_for'), 'F')}\n"
            f"• Gestartet: {_fmt_dt(event.get('started_at'), 'F')}\n"
            f"• Beendet: {_fmt_dt(event.get('ended_at'), 'F')}\n"
            f"• Dauer: **{_fmt_duration(event.get('duration_seconds'))}**"
        ),
        inline=False,
    )
    embed.add_field(name="Sprecher", value=_speaker_lines(event.get("speaker_snapshot")), inline=False)
    return embed


def build_topics_embed(settings, guild: discord.Guild | None, rows: list[dict], *, title: str) -> discord.Embed:
    if not rows:
        return discord.Embed(title=title, description="Keine Einträge gefunden.", color=_color(settings, guild))
    lines: list[str] = []
    for item in rows[:10]:
        lines.append(
            f"`#{int(item.get('id') or 0)}` **{_truncate(item.get('title', ''), 60)}**\n"
            f"Status: **{item.get('status', 'pending')}** • Von: <@{int(item.get('submitted_by') or 0)}> • {_fmt_dt(item.get('created_at'), 'd')}\n"
            f"{_truncate(item.get('description', '—'), 120)}"
        )
    if len(rows) > 10:
        lines.append(f"+{len(rows) - 10} weitere Einträge")
    return discord.Embed(title=title, description="\n\n".join(lines), color=_color(settings, guild))
