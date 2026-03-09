from __future__ import annotations

import discord

from bot.utils.emojis import em


DEFAULT_COLOR = 0x5C8CFF
NEBULITON_URL = "https://nebuliton.io"
NEBULITON_LOGO_URL = "https://nebuliton.io/logo.png"


def parse_hex_color(value: str | None, default: int = DEFAULT_COLOR) -> int:
    if not value:
        return default
    raw = str(value).strip().replace("#", "")
    try:
        return int(raw, 16)
    except Exception:
        return default


def _color(settings, guild: discord.Guild | None) -> int:
    if guild:
        sponsor_value = settings.get_guild(guild.id, "sponsor.nebu.accent_color", None)
        if sponsor_value:
            return parse_hex_color(str(sponsor_value), DEFAULT_COLOR)
        value = settings.get_guild(guild.id, "design.accent_color", "#B16B91")
    else:
        sponsor_value = settings.get("sponsor.nebu.accent_color", None)
        if sponsor_value:
            return parse_hex_color(str(sponsor_value), DEFAULT_COLOR)
        value = settings.get("design.accent_color", "#B16B91")
    return parse_hex_color(str(value), DEFAULT_COLOR)


def _add_logo(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=NEBULITON_LOGO_URL)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def _hero_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    hearts = em(settings, "hearts", guild) or "💙"

    header = f"**{info} 𑁉 NEBULITON HOSTING • UNSER PARTNER**"
    intro = (
        f"{arrow2} **Nebuliton Hosting** ist unser offizieller Partner für starke Hosting-Lösungen "
        "mit fairen Preisen und sauberer Performance.\n"
        f"{hearts} Wenn du geile Server für einen guten Preis suchst, findest du dort alles "
        "vom kleinen Projekt bis zur großen Infrastruktur."
    )
    meta = (
        "┏`🤝` - Offizieller Partner unseres Servers\n"
        "┣`⚡` - Performance, Stabilität und moderne Infrastruktur\n"
        "┗`💸` - Starkes Preis-Leistungs-Verhältnis"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_logo(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Partner-Highlights**\n{meta}"))
    container.add_item(discord.ui.Separator())

    row = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Button(
            label="Website öffnen",
            style=discord.ButtonStyle.link,
            url=NEBULITON_URL,
            emoji="🌐",
        )
    )
    row.add_item(
        discord.ui.Button(
            label="Logo öffnen",
            style=discord.ButtonStyle.link,
            url=NEBULITON_LOGO_URL,
            emoji="🖼️",
        )
    )
    container.add_item(row)
    return container


def _products_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    chat = em(settings, "chat", guild) or "💬"

    offers = (
        "┏`🤖` - Discord-Bot Hosting für zuverlässige 24/7-Projekte\n"
        "┣`🌐` - Webhosting für Websites, Dashboards und Tools\n"
        "┣`⛏️` - Minecraft Server Hosting für Communitys und Welten\n"
        "┣`🖥️` - Root Server mit voller Kontrolle und Flexibilität\n"
        "┣`🧱` - Dedicated Server für maximale Power\n"
        "┗`🎮` - Neu: Remote Gaming"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"**{chat} 𑁉 HOSTING-ANGEBOT**\n{offers}"))
    return container


def _cta_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    money = em(settings, "money", guild) or "💸"
    arrow2 = em(settings, "arrow2", guild) or "»"

    why = (
        "┏`🧩` - Ideal für Discord-Communitys, Entwickler und Gamer\n"
        "┣`🚀` - Geeignet für kleine Projekte und große Setups\n"
        "┣`🛡️` - Eine starke Option, wenn dir Stabilität wichtig ist\n"
        "┗`🎯` - Alles an einem Ort statt bei fünf verschiedenen Hostern"
    )
    closing = (
        f"{money} Ob Bot Hosting, Webhosting, Minecraft, Root Server, Dedicated Server "
        "oder das neue Remote Gaming: Bei **Nebuliton** bekommst du die volle Auswahl.\n"
        f"{arrow2} Jetzt entdecken: {NEBULITON_URL}"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"**💡 𑁉 WARUM NEBULITON?**\n{why}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**{money} 𑁉 JETZT ENTDECKEN**\n{closing}"))
    return container


def build_nebuliton_view(settings, guild: discord.Guild | None) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(_hero_container(settings, guild))
    view.add_item(_products_container(settings, guild))
    view.add_item(_cta_container(settings, guild))
    return view
