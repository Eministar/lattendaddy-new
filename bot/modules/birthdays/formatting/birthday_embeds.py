from __future__ import annotations

import calendar
import discord
from bot.utils.emojis import em
from bot.utils.assets import Banners


def _add_banner(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=Banners.BIRTHDAY_BANNER)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def _boxed_lines(lines: list[str], empty_text: str) -> str:
    if not lines:
        return f"┗{empty_text}"
    out: list[str] = []
    total = len(lines)
    for idx, line in enumerate(lines):
        if total == 1:
            prefix = "┗"
        elif idx == 0:
            prefix = "┏"
        elif idx == total - 1:
            prefix = "┗"
        else:
            prefix = "┣"
        out.append(f"{prefix}{line}")
    return "\n".join(out)


def build_birthday_announcement_view(
    settings,
    guild: discord.Guild | None,
    accent_color: int,
    today_entries: list[dict],
    next_entries: list[dict],
    total_birthdays: int | None = None,
):
    cake = em(settings, "cake", guild) or "🎂"
    party = em(settings, "party", guild) or "🎉"
    heart = em(settings, "hearts", guild) or "💖"
    arrow2 = em(settings, "arrow2", guild) or "»"
    calendar_emoji = em(settings, "calendar", guild) or "🗓️"

    header = f"**{cake} 𑁉 GEBURTSTAGSPANEL**"
    intro = f"{arrow2} Hier siehst du die Geburtstage von heute und die nächsten anstehenden Feiern."
    total_text = f"{calendar_emoji} **Eingetragene Geburtstage:** `{int(total_birthdays or 0)}`"
    congrats = f"{party} **Happy Birthday!** {heart}" if today_entries else f"{heart} **Heute ist noch alles ruhig.**"

    today_lines: list[str] = []
    for entry in today_entries:
        member = entry.get("member")
        user_id = int(entry.get("user_id") or 0)
        mention = member.mention if member else f"<@{user_id}>"
        age = entry.get("age")
        if age is not None:
            today_lines.append(f"{party} - {mention} wird **{int(age)}**")
        else:
            today_lines.append(f"{party} - {mention}")

    today_block = _boxed_lines(today_lines, "🎈 - Heute hat niemand Geburtstag.")
    next_lines: list[str] = []
    for entry in next_entries:
        member = entry.get("member")
        user_id = int(entry.get("user_id") or 0)
        mention = member.mention if member else f"<@{user_id}>"
        day = int(entry.get("day") or 0)
        month = int(entry.get("month") or 0)
        days_until = int(entry.get("days_until") or 0)
        turns = entry.get("turns")
        when_text = f"am **{day:02d}.{month:02d}.**"
        if turns is not None:
            next_lines.append(f"{calendar_emoji} - {mention} in **{days_until}** Tagen, {when_text} und wird **{int(turns)}**")
        else:
            next_lines.append(f"{calendar_emoji} - {mention} in **{days_until}** Tagen, {when_text}")
    next_block = _boxed_lines(next_lines, "🗓️ - Es sind noch keine weiteren Geburtstage eingetragen.")

    container = discord.ui.Container(accent_colour=accent_color)
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}\n\n{congrats}\n{total_text}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Heute**\n{today_block}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Demnächst**\n{next_block}"))

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view
