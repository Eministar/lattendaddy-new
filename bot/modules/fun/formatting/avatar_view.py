from __future__ import annotations

import discord

from bot.utils.emojis import em


def _color(settings, guild: discord.Guild | None) -> int:
    gid = guild.id if guild else 0
    raw = str(settings.get_guild(gid, "design.accent_color", "#B16B91") or "").replace("#", "").strip()
    try:
        return int(raw, 16)
    except Exception:
        return 0xB16B91


def _wrap(container: discord.ui.Container) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def _asset_url(asset: discord.Asset | None, *, size: int = 4096) -> str | None:
    if not asset:
        return None
    try:
        return str(asset.replace(size=size).url)
    except Exception:
        try:
            return str(asset.url)
        except Exception:
            return None


def _is_animated(asset: discord.Asset | None) -> bool:
    if not asset:
        return False
    try:
        return bool(asset.is_animated())
    except Exception:
        return False


def build_avatar_view(
    settings,
    guild: discord.Guild | None,
    subject: discord.User | discord.Member,
    member: discord.Member | None = None,
) -> discord.ui.LayoutView:
    profile = member or subject

    arrow2 = em(settings, "arrow2", guild) or "»"
    sparkles = em(settings, "sparkles", guild) or "✨"

    display_name = getattr(profile, "display_name", None) or getattr(subject, "display_name", None) or getattr(subject, "name", None) or f"User {subject.id}"
    mention = getattr(profile, "mention", None) or getattr(subject, "mention", None) or f"<@{subject.id}>"
    display_avatar_url = _asset_url(profile.display_avatar)
    global_avatar_url = _asset_url(getattr(subject, "avatar", None)) or display_avatar_url
    guild_avatar_url = _asset_url(getattr(member, "guild_avatar", None)) if member else None
    banner_url = _asset_url(getattr(subject, "banner", None))

    uses_guild_avatar = bool(guild_avatar_url and display_avatar_url and guild_avatar_url == display_avatar_url)
    avatar_type = "Server-Profilbild" if uses_guild_avatar else "Globales Profilbild"
    banner_state = "Gesetzt" if banner_url else "Nicht gesetzt"

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    intro = (
        f"{arrow2} Profilbild und Banner von {mention} in hoher Auflösung.\n\n"
        f"┏`👤` - Anzeige: **{display_name}**\n"
        f"┣`🆔` - ID: `{subject.id}`\n"
        f"┣`📸` - Profilbild: **{avatar_type}**\n"
        f"┣`🎨` - Banner: **{banner_state}**\n"
        f"┗`📐` - Qualität: **bis zu 4096 px**"
    )

    if display_avatar_url:
        container.add_item(
            discord.ui.Section(
                "**🖼️ 𑁉 PROFILANSICHT**",
                intro,
                accessory=discord.ui.Thumbnail(
                    media=display_avatar_url,
                    description=f"Profilbild von {display_name}",
                ),
            )
        )
    else:
        container.add_item(discord.ui.TextDisplay(f"**🖼️ 𑁉 PROFILANSICHT**\n{intro}"))

    gallery_added = False
    try:
        gallery = discord.ui.MediaGallery()
        if display_avatar_url:
            gallery.add_item(media=display_avatar_url)
            gallery_added = True
        if banner_url:
            gallery.add_item(media=banner_url)
            gallery_added = True
        if gallery_added:
            container.add_item(discord.ui.Separator())
            container.add_item(gallery)
    except Exception:
        gallery_added = False

    detail_lines = [
        f"┏`✨` - Sichtbar ist das aktuell aktive Profilbild von {mention}.",
        f"┣`🎞️` - Avatar animiert: **{'Ja' if _is_animated(profile.display_avatar) else 'Nein'}**",
        f"┣`🪄` - Banner animiert: **{'Ja' if _is_animated(getattr(subject, 'banner', None)) else 'Nein'}**",
        f"┗`🔎` - Direktlinks unten öffnen die Dateien separat im Browser.",
    ]
    if guild_avatar_url and global_avatar_url and guild_avatar_url != global_avatar_url:
        detail_lines[0] = f"┏`✨` - {sparkles} Server-Profilbild und globales Profilbild unterscheiden sich."
    if not banner_url:
        detail_lines[2] = "┣`🪄` - Banner animiert: **Nein, weil kein Banner gesetzt ist**"

    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay("**`📋` DETAILS**\n" + "\n".join(detail_lines)))

    row = discord.ui.ActionRow()
    button_count = 0
    if display_avatar_url:
        row.add_item(
            discord.ui.Button(
                label="Profilbild öffnen",
                style=discord.ButtonStyle.link,
                url=display_avatar_url,
                emoji="🖼️",
            )
        )
        button_count += 1
    if guild_avatar_url and global_avatar_url and guild_avatar_url != global_avatar_url:
        row.add_item(
            discord.ui.Button(
                label="Global öffnen",
                style=discord.ButtonStyle.link,
                url=global_avatar_url,
                emoji="🌐",
            )
        )
        button_count += 1
    if banner_url:
        row.add_item(
            discord.ui.Button(
                label="Banner öffnen",
                style=discord.ButtonStyle.link,
                url=banner_url,
                emoji="🎨",
            )
        )
        button_count += 1
    if button_count:
        container.add_item(discord.ui.Separator())
        container.add_item(row)

    return _wrap(container)
