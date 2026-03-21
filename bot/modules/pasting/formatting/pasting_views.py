from __future__ import annotations

import discord

from bot.utils.assets import Banners
from bot.utils.emojis import em


def parse_hex_color(value: str | None, default: int = 0xB16B91) -> int:
    if not value:
        return default
    raw = str(value).strip().replace("#", "")
    try:
        return int(raw, 16)
    except Exception:
        return default


def _color(settings, guild: discord.Guild | None) -> int:
    if guild:
        value = settings.get_guild(guild.id, "design.accent_color", "#B16B91")
    else:
        value = settings.get("design.accent_color", "#B16B91")
    return parse_hex_color(value)


def _clip(text: str | None, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _add_banner(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=Banners.SUPPORT)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def _wrap(container: discord.ui.Container) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def _link_rows(links: list[dict[str, str]]) -> list[discord.ui.ActionRow]:
    rows: list[discord.ui.ActionRow] = []
    for offset in range(0, min(len(links), 25), 5):
        row = discord.ui.ActionRow()
        for index, link in enumerate(links[offset: offset + 5], start=offset + 1):
            label = "StarPaste öffnen" if len(links) == 1 else f"Paste {index}"
            row.add_item(
                discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.link,
                    url=str(link.get("url") or ""),
                    emoji="🔗",
                )
            )
        rows.append(row)
    return rows


def _title_block(links: list[dict[str, str]]) -> str:
    if not links:
        return "Noch keine Pastes erstellt."
    lines: list[str] = []
    shown = links[:8]
    last_index = len(shown) - 1
    for index, link in enumerate(shown):
        prefix = "┗" if index == last_index and len(links) <= 8 else "┣"
        if index == 0:
            prefix = "┏"
        title = _clip(link.get("title") or f"Paste {index + 1}", 70)
        lines.append(f"{prefix}`📄` - `{title}`")
    if len(links) > 8:
        lines.append(f"┗`➕` - Weitere Teile: **{len(links) - 8}**")
    return "\n".join(lines)


def build_pasting_loading_view(
    settings,
    guild: discord.Guild | None,
    *,
    author_name: str,
    detected_labels: list[str],
    item_count: int,
):
    loading = em(settings, "loading", guild) or "⏳"
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"

    reason_text = ", ".join(detected_labels) if detected_labels else "Inhalt"
    header = f"**{loading} 𑁉 STARPASTE-UPLOAD**"
    intro = f"{arrow2} Ich habe {reason_text} erkannt und lade den Inhalt gerade auf StarPaste hoch."
    details = (
        f"┏`👤` - Von: **{_clip(author_name, 48)}**\n"
        f"┣`🧠` - Erkannt: **{_clip(reason_text, 120)}**\n"
        f"┗`📦` - Uploads vorbereitet: **{max(1, int(item_count))}**"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**{info} Status**\n{details}"))
    return _wrap(container)


def build_pasting_result_view(
    settings,
    guild: discord.Guild | None,
    *,
    status: str,
    author_name: str,
    detected_labels: list[str],
    links: list[dict[str, str]],
    original_deleted: bool,
    skipped_items: list[str] | None = None,
    error_text: str | None = None,
):
    state = str(status or "success").strip().lower()
    arrow2 = em(settings, "arrow2", guild) or "»"
    green = em(settings, "green", guild) or "🟢"
    orange = em(settings, "orange", guild) or "🟠"
    red = em(settings, "red", guild) or "🔴"
    info = em(settings, "info", guild) or "ℹ️"

    if state == "partial":
        marker = orange
        title = "STARPASTE-UPLOAD TEILWEISE"
        intro = f"{arrow2} Ein Teil wurde hochgeladen, aber nicht alles konnte sauber abgeschlossen werden."
    elif state == "error":
        marker = red
        title = "STARPASTE-UPLOAD FEHLER"
        intro = f"{arrow2} Der Upload zu StarPaste ist fehlgeschlagen. Die Originalnachricht bleibt erhalten."
    else:
        marker = green
        title = "STARPASTE-UPLOAD FERTIG"
        intro = f"{arrow2} Der Inhalt wurde erfolgreich auf StarPaste ausgelagert."

    reasons = ", ".join(detected_labels) if detected_labels else "Inhalt"
    delete_line = (
        f"{green} Die Originalnachricht wurde gelöscht, damit der Kanal sauber bleibt."
        if original_deleted
        else f"{orange} Die Originalnachricht konnte nicht gelöscht werden."
    )
    if state == "error":
        delete_line = f"{red} Die Originalnachricht wurde nicht angerührt."

    details = (
        f"┏`👤` - Von: **{_clip(author_name, 48)}**\n"
        f"┣`🧠` - Erkannt: **{_clip(reasons, 120)}**\n"
        f"┣`📦` - Pastes erstellt: **{len(links)}**\n"
        f"┗`🔗` - Öffnen: {'Buttons unten' if links else 'Kein Link vorhanden'}"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container)
    container.add_item(discord.ui.TextDisplay(f"**{marker} 𑁉 {title}**\n{intro}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**{info} Übersicht**\n{details}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Dateien / Teile**\n{_title_block(links)}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(delete_line))

    if skipped_items:
        preview = "\n".join(f"• {_clip(item, 110)}" for item in skipped_items[:6])
        if len(skipped_items) > 6:
            preview += f"\n• Weitere Hinweise: {len(skipped_items) - 6}"
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"**Hinweise**\n{preview}"))

    if error_text:
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"**Fehlerdetails**\n{_clip(error_text, 300)}"))

    rows = _link_rows(links)
    for row in rows:
        container.add_item(discord.ui.Separator())
        container.add_item(row)

    return _wrap(container)
