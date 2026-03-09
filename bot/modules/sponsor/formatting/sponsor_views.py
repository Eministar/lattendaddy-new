from __future__ import annotations

import discord

from bot.utils.emojis import em


DEFAULT_COLOR = 0xF59E0B
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


def _footer(emb: discord.Embed, settings, guild: discord.Guild | None):
    bot_member = getattr(guild, "me", None) if guild else None
    footer = f"Offizieller Partner von {guild.name}" if guild else "Offizieller Partner"
    try:
        custom_footer = settings.get_guild(guild.id, "design.footer_text", None) if guild else settings.get("design.footer_text", None)
    except Exception:
        custom_footer = None
    text = str(custom_footer).strip() if custom_footer else footer
    if bot_member:
        emb.set_footer(text=text, icon_url=bot_member.display_avatar.url)
    else:
        emb.set_footer(text=text)


def build_nebuliton_embed(settings, guild: discord.Guild | None) -> discord.Embed:
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    money = em(settings, "money", guild) or "💸"
    hearts = em(settings, "hearts", guild) or "💜"
    chat = em(settings, "chat", guild) or "💬"

    desc = (
        f"{arrow2} **Nebuliton Hosting** ist unser offizieller Partner für starkes Hosting "
        "mit fairen Preisen und sauberer Performance.\n"
        f"{hearts} Wenn du zuverlässige Server für Bots, Websites, Games oder große Projekte suchst, "
        "bist du dort genau richtig."
    )

    emb = discord.Embed(
        title=f"{info} 𑁉 NEBULITON HOSTING • UNSER PARTNER",
        url=NEBULITON_URL,
        description=desc,
        color=_color(settings, guild),
    )
    emb.set_thumbnail(url=NEBULITON_LOGO_URL)
    emb.add_field(
        name=f"{chat} Hosting-Angebot",
        value=(
            "• Discord-Bot Hosting\n"
            "• Webhosting\n"
            "• Minecraft Server Hosting\n"
            "• Root Server\n"
            "• Dedicated Server\n"
            "• Remote Gaming"
        ),
        inline=False,
    )
    emb.add_field(
        name="💡 Warum Nebuliton?",
        value=(
            "• Faire Preise bei starker Leistung\n"
            "• Stabil, modern und zuverlässig\n"
            "• Für kleine Projekte und große Setups geeignet"
        ),
        inline=False,
    )
    emb.add_field(
        name=f"{money} Perfekt für",
        value=(
            "• Discord-Communitys und Bot-Entwickler\n"
            "• Websites, Panels und Web-Projekte\n"
            "• Minecraft-Server und anspruchsvolle Infrastruktur"
        ),
        inline=False,
    )
    _footer(emb, settings, guild)
    return emb


def build_nebuliton_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(
            label="Jetzt entdecken",
            style=discord.ButtonStyle.link,
            url=NEBULITON_URL,
            emoji="🌐",
        )
    )
    return view
