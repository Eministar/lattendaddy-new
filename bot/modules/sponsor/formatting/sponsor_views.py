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
        f"{arrow2} **Nebuliton Hosting** ist unser offizieller Partner für Hosting mit fairen Preisen, "
        "starker Performance und moderner Infrastruktur.\n"
        f"{hearts} Wenn du starke Server für einen guten Preis suchst, bist du dort genau richtig."
    )
    overview = (
        "┏`🤝` - Offizieller Partner unseres Servers\n"
        "┣`⚡` - Stabil, modern und leistungsstark\n"
        "┗`💸` - Sehr gutes Preis-Leistungs-Verhältnis"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_logo(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Auf einen Blick**\n{overview}"))

    row = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Button(
            label="Nebuliton besuchen",
            style=discord.ButtonStyle.link,
            url=NEBULITON_URL,
            emoji="🌐",
        )
    )
    container.add_item(row)
    return container


def _products_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    chat = em(settings, "chat", guild) or "💬"

    community = (
        "┏`🤖` - Discord-Bot Hosting\n"
        "┣`🌐` - Webhosting\n"
        "┗`⛏️` - Minecraft Server Hosting"
    )
    server = (
        "┏`🖥️` - Root Server\n"
        "┣`🧱` - Dedicated Server\n"
        "┗`🎮` - Remote Gaming"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"**{chat} 𑁉 HOSTING-ANGEBOT**"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Für Communitys & Projekte**\n{community}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**Für Power-User & große Setups**\n{server}"))
    return container


def _benefits_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    money = em(settings, "money", guild) or "💸"

    why = (
        "┏`🧩` - Alles an einem Ort statt bei mehreren Anbietern\n"
        "┣`🚀` - Geeignet für kleine Projekte und große Setups\n"
        "┣`🛡️` - Stark, wenn dir Stabilität und Performance wichtig sind\n"
        "┗`🎯` - Ideal für Entwickler, Communitys und Gamer"
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"**💡 𑁉 WARUM NEBULITON?**\n{why}"))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.TextDisplay(
            f"**{money} 𑁉 PREIS & LEISTUNG**\n"
            "Wenn du gute Server zu einem fairen Preis willst, ist Nebuliton eine sehr starke Adresse."
        )
    )
    return container


def _cta_container(settings, guild: discord.Guild | None) -> discord.ui.Container:
    money = em(settings, "money", guild) or "💸"
    arrow2 = em(settings, "arrow2", guild) or "»"

    closing = (
        f"{money} Ob Bot Hosting, Webhosting, Minecraft, Root Server, Dedicated Server oder "
        "Remote Gaming: Bei **Nebuliton** findest du das passende Setup.\n"
        f"{arrow2} Mehr Infos direkt auf der Website."
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"**{money} 𑁉 JETZT ENTDECKEN**\n{closing}"))
    row = discord.ui.ActionRow()
    row.add_item(
        discord.ui.Button(
            label="Zur Website",
            style=discord.ButtonStyle.link,
            url=NEBULITON_URL,
            emoji="🌐",
        )
    )
    container.add_item(row)
    return container


def build_nebuliton_view(settings, guild: discord.Guild | None) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(_hero_container(settings, guild))
    view.add_item(_products_container(settings, guild))
    view.add_item(_benefits_container(settings, guild))
    view.add_item(_cta_container(settings, guild))
    return view
