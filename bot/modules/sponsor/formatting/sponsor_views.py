from __future__ import annotations

import discord

DEFAULT_COLOR = 0xF97316
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
    else:
        sponsor_value = settings.get("sponsor.nebu.accent_color", None)
        if sponsor_value:
            return parse_hex_color(str(sponsor_value), DEFAULT_COLOR)
    return DEFAULT_COLOR


def build_nebuliton_view(settings, guild: discord.Guild | None) -> discord.ui.LayoutView:
    header = (
        "**☁️ 𑁉 NEBULITON HOSTING**\n"
        "Offizieller Partner unseres Servers für modernes Hosting mit starker Performance und fairen Preisen."
    )
    intro = (
        "Wenn du saubere Lösungen für Bots, Websites, Minecraft oder größere Infrastruktur suchst, "
        "ist Nebuliton eine starke Adresse."
    )
    products = (
        "**`📦` ANGEBOTE**\n"
        "`🤖` Discord-Bot Hosting\n"
        "`🌐` Webhosting\n"
        "`⛏️` Minecraft Server Hosting\n"
        "`🖥️` Root Server\n"
        "`🧱` Dedicated Server\n"
        "`🎮` Remote Gaming"
    )
    reasons = (
        "**`✨` WARUM NEBULITON?**\n"
        "`•` Faire Preise bei starker Leistung\n"
        "`•` Stabil, modern und zuverlässig\n"
        "`•` Geeignet für kleine Projekte und große Setups"
    )
    audience = (
        "**`🎯` PASSEND FÜR**\n"
        "`•` Discord-Communitys und Bot-Projekte\n"
        "`•` Websites, Panels und Web-Tools\n"
        "`•` Minecraft-Server und anspruchsvolle Infrastruktur"
    )
    cta = (
        "**`🚀` JETZT ENTDECKEN**\n"
        "Wenn du gutes Hosting mit sauberem Preis-Leistungs-Verhältnis suchst, schau bei Nebuliton vorbei."
    )

    view = discord.ui.LayoutView(timeout=None)
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(
        discord.ui.Section(
            header,
            intro,
            accessory=discord.ui.Thumbnail(media=NEBULITON_LOGO_URL, description="Nebuliton Logo"),
        )
    )
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(products))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(reasons))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(audience))
    container.add_item(discord.ui.Separator())
    container.add_item(
        discord.ui.Section(
            cta,
            accessory=discord.ui.Button(
                label="Website öffnen",
                style=discord.ButtonStyle.link,
                url=NEBULITON_URL,
                emoji="🌐",
            ),
        )
    )
    view.add_item(container)
    return view
