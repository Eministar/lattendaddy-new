import discord
from discord.utils import format_dt
from datetime import datetime
from bot.utils.emojis import em
from bot.utils.assets import Banners


def parse_hex_color(value: str, default: int = 0xB16B91) -> int:
    if not value:
        return default
    v = str(value).strip().replace("#", "")
    try:
        return int(v, 16)
    except Exception:
        return default


def _color(settings, guild: discord.Guild | None):
    if guild:
        value = settings.get_guild(guild.id, "design.accent_color", "#B16B91")
    else:
        value = settings.get("design.accent_color", "#B16B91")
    return parse_hex_color(value)


def _footer(emb: discord.Embed, settings, guild: discord.Guild | None):
    if guild:
        ft = settings.get_guild(guild.id, "design.footer_text", None)
        bot_member = getattr(guild, "me", None)
    else:
        ft = settings.get("design.footer_text", None)
        bot_member = None
    if ft:
        if bot_member:
            emb.set_footer(text=bot_member.display_name, icon_url=bot_member.display_avatar.url)
        else:
            emb.set_footer(text=str(ft))


def _add_banner(container: discord.ui.Container, banner_url: str | None):
    if not banner_url:
        return
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=banner_url)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def _wrap(container: discord.ui.Container) -> discord.ui.LayoutView:
    view = discord.ui.LayoutView(timeout=None)
    view.add_item(container)
    return view


def build_summary_container(
    settings,
    guild: discord.Guild | None,
    user: discord.User,
    member: discord.Member | None,
    category_label: str,
    created_at: datetime,
    total_tickets: int,
    priority: int | None = None,
    status_label: str | None = None,
    escalated_level: int | None = None,
):
    book = em(settings, "book", guild)
    arrow2 = em(settings, "arrow2", guild)

    joined = format_dt(member.joined_at, style="R") if member and member.joined_at else "unbekannt"

    desc = (
        f"{arrow2} Ich habe ein paar nützliche Details über diese Support-Anfrage zusammengetragen. 📝\n\n"
        f"┏`👥` - Profil: {user.mention} ({user.id})\n"
        f"┣`🌈` - Account erstellt: {format_dt(user.created_at, style='R')}\n"
        f"┣`🏆` - Server beigetreten: {joined}\n"
        f"┗`📬` - Hat bereits {total_tickets} Tickets erstellt.\n\n"
        f"┏`📚` - Ticket-Thema: {category_label}\n"
        f"┣`🚦` - Priorität: { _priority_label(priority) }\n"
        f"┣`🏷️` - Status: {status_label if status_label else '🟢 OFFEN'}\n"
        f"┣`⚠️` - Eskalation: {int(escalated_level) if escalated_level else 0}\n"
        f"┗`⏰` - Ticket erstellt: {format_dt(created_at, style='f')}\n\n"
        "Nutze die Buttons unten für Claim, Status, Priorität, Eskalation oder Transcript."
    )

    header = f"**{book} 𑁉 SUPPORT-TICKET - ZUSAMMENFASSUNG**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, Banners.TICKETS_STAFF)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return container


def build_summary_embed(
    settings,
    guild: discord.Guild | None,
    user: discord.User,
    member: discord.Member | None,
    category_label: str,
    created_at: datetime,
    total_tickets: int,
    priority: int | None = None,
    status_label: str | None = None,
    escalated_level: int | None = None,
):
    return _wrap(
        build_summary_container(
            settings,
            guild,
            user,
            member,
            category_label,
            created_at,
            total_tickets,
            priority=priority,
            status_label=status_label,
            escalated_level=escalated_level,
        )
    )


def _priority_label(priority: int | None) -> str:
    mapping = {
        1: "Niedrig",
        2: "Normal",
        3: "Hoch",
        4: "Dringend",
    }
    try:
        return mapping.get(int(priority or 2), "Normal")
    except Exception:
        return "Normal"


def build_user_message_embed(settings, guild: discord.Guild | None, user: discord.User, content: str):
    arrow2 = em(settings, "arrow2", guild) or "»"
    desc = f"{arrow2} {content}" if content else f"{arrow2} "
    header = f"**{user.display_name}** · <@{user.id}>"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_created_embed(settings, guild: discord.Guild | None, ticket_id: int, created_at: datetime):
    book = em(settings, "book", guild)
    arrow2 = em(settings, "arrow2", guild) or "»"

    desc = (
        f"{arrow2} Dein Ticket wurde erstellt – unser Team antwortet dir hier per DM.\n\n"
        f"┏`📚` - Ticket-ID: `{ticket_id}`\n"
        f"┣`⏰` - Erstellt: {format_dt(created_at, style='f')}\n"
        f"┗`🟢` - Status: OFFEN\n\n"
        f"Schreib einfach hier weiter, ich häng’s automatisch ans Ticket."
    )

    header = f"**{book} 𑁉 SUPPORT-TICKET - BESTÄTIGUNG**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, Banners.TICKETS_OPENED)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_confirmation_container(
    settings,
    guild: discord.Guild | None,
    category_label: str,
    preview_text: str | None,
    attachment_count: int = 0,
    state: str = "pending",
    ticket_id: int | None = None,
):
    book = em(settings, "book", guild) or "📚"
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"
    sparkles = em(settings, "sparkles", guild) or "✨"
    green = em(settings, "green", guild) or "🟢"
    orange = em(settings, "orange", guild) or "🟠"

    preview = (preview_text or "").strip() or "Kein Text, nur Anhänge."
    details = (
        f"┏`🧭` - Bereich: **{category_label}**\n"
        f"┣`📝` - Vorschau: {preview}\n"
        f"┗`📎` - Anhänge: **{int(max(0, attachment_count))}**"
    )

    current_state = str(state or "pending").lower()
    if current_state == "created":
        header = f"**{book} 𑁉 SUPPORT-TICKET - ERSTELLT**"
        intro = f"{arrow2} Dein Ticket wurde gerade eröffnet und ans Team weitergegeben."
        meta = f"┗`📚` - Ticket-ID: `{int(ticket_id or 0)}`"
        note = f"{green} Schreib einfach hier weiter. Neue Nachrichten werden automatisch übernommen."
    elif current_state == "appended":
        header = f"**{info} 𑁉 SUPPORT-TICKET - AKTUALISIERT**"
        intro = f"{arrow2} Du hattest bereits ein offenes Ticket. Ich habe deine Nachricht dort ergänzt."
        meta = f"┗`📚` - Ticket-ID: `{int(ticket_id or 0)}`"
        note = f"{green} Antworten vom Team bekommst du weiterhin hier in der DM."
    elif current_state == "cancelled":
        header = f"**{info} 𑁉 SUPPORT-TICKET - ABBRUCH**"
        intro = f"{arrow2} Alles gut. Ich habe kein Ticket erstellt."
        meta = None
        note = f"{orange} Wenn du doch Hilfe brauchst, schick mir einfach eine neue Nachricht."
    elif current_state == "expired":
        header = f"**{info} 𑁉 SUPPORT-TICKET - ABGELAUFEN**"
        intro = f"{arrow2} Diese Bestätigung ist nicht mehr gültig."
        meta = None
        note = f"{orange} Schick dein Anliegen einfach nochmal, dann starte ich den Ablauf neu."
    else:
        header = f"**{book} 𑁉 SUPPORT-TICKET - BESTÄTIGUNG**"
        intro = f"{arrow2} Ich habe dein Anliegen vorbereitet. Bestätige unten, dann eröffne ich dein Ticket."
        meta = (
            f"┏`✅` - Button: `Ticket eröffnen`\n"
            f"┣`📬` - Deine Nachricht wird übernommen\n"
            f"┗`🧵` - Antworten kommen danach hier per DM"
        )
        note = f"{sparkles} Prüfe kurz die Vorschau unten, bevor du bestätigst."

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, Banners.TICKETS_OPENED)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**DEINE ANFRAGE**\n{details}"))
    if meta:
        container.add_item(discord.ui.Separator())
        container.add_item(discord.ui.TextDisplay(f"**STATUS**\n{meta}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(note))
    return container


def build_dm_message_appended_embed(settings, guild: discord.Guild | None, ticket_id: int):
    arrow2 = em(settings, "arrow2", guild) or "»"
    info = em(settings, "info", guild) or "ℹ️"

    desc = (
        f"{arrow2} Hab’s ans Ticket gehängt.\n\n"
        f"┏`📚` - Ticket-ID: `{ticket_id}`\n"
        f"┗`✅` - Info: Du bekommst Antworten vom Team hier per DM."
    )

    header = f"**{info} 𑁉 NACHRICHT ÜBERNOMMEN**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_staff_reply_embed(settings, guild: discord.Guild | None, staff: discord.Member, ticket_id: int, text: str, reply_line: str | None = None):
    love = em(settings, "discord_love", guild)
    arrow2 = em(settings, "arrow2", guild) or "»"

    reply_block = f"{reply_line}\n\n" if reply_line else ""
    desc = (
        f"{reply_block}{arrow2} {text if text else ' '}\n\n"
        f"┏`👤` - Teamer: **{staff.display_name}**\n"
        f"┗`📚` - Ticket-ID: `{ticket_id}`"
    )

    header = f"**{love} 𑁉 TEAM-ANTWORT**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, Banners.TICKETS_ANSWER)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_closed_container(
    settings,
    guild: discord.Guild | None,
    ticket_id: int,
    closed_at: datetime,
    rating_enabled: bool,
):
    red = em(settings, "red", guild) or "🔴"
    arrow2 = em(settings, "arrow2", guild) or "»"

    tail = "Bewerte den Support unten mit ⭐." if rating_enabled else "Wenn du nochmal was brauchst, schreib einfach neu."
    desc = (
        f"{arrow2} Ticket ist zu. Danke dir! 💜\n\n"
        f"┏`📚` - Ticket-ID: `{ticket_id}`\n"
        f"┗`⏰` - Geschlossen: {format_dt(closed_at, style='f')}\n\n"
        f"{tail}"
    )

    header = f"**{red} 𑁉 TICKET GESCHLOSSEN**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, Banners.TICKETS_CLOSED)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return container


def build_dm_ticket_closed_embed(settings, guild: discord.Guild | None, ticket_id: int, closed_at: datetime, rating_enabled: bool):
    return _wrap(build_dm_ticket_closed_container(settings, guild, ticket_id, closed_at, rating_enabled))


def build_dm_rating_thanks_embed(settings, guild: discord.Guild | None, rating: int):
    cheers = em(settings, "cheers", guild) or "🎉"
    arrow2 = em(settings, "arrow2", guild) or "»"

    desc = (
        f"{arrow2} Danke für deine Bewertung! 💜\n\n"
        f"┏`⭐` - Bewertung: **{rating}/5**\n"
        f"┗`📌` - Info: Hilft uns extrem, den Support besser zu machen."
    )

    header = f"**{cheers} 𑁉 BEWERTUNG GESPEICHERT**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_added_embed(settings, guild: discord.Guild | None, ticket_id: int, added_by: discord.Member):
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    desc = (
        f"{arrow2} Du wurdest zu einem Ticket hinzugefügt.\n\n"
        f"• Ticket-ID: `{ticket_id}`\n"
        f"• Hinzugefügt von: **{added_by.display_name}**\n\n"
        f"Schreib einfach hier, deine Nachricht landet im Ticket."
    )
    header = f"**{info} TICKET-ZUGANG**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_thread_status_embed(
    settings,
    guild: discord.Guild | None,
    title: str,
    text: str,
    actor: discord.Member | None = None,
    banner_url: str | None = None,
):
    arrow2 = em(settings, "arrow2", guild) or "»"
    header = f"**{title}**"
    body = f"{arrow2} {text}"
    if actor:
        body = f"{body}\n\n┗`👤` - {actor.display_name}"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, banner_url)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{body}"))
    return _wrap(container)


def build_thread_rating_embed(settings, guild: discord.Guild | None, user_id: int, rating: int, comment: str | None):
    hearts = em(settings, "hearts", guild) or "💜"

    desc = f"┏`⭐` - Bewertung: **{rating}/5**\n┗`👤` - User: <@{user_id}>"
    if comment:
        desc += f"\n\n{comment}"

    header = f"**{hearts} 𑁉 BEWERTUNG**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_update_embed(
    settings,
    guild: discord.Guild | None,
    title: str,
    text: str,
    banner_url: str | None = None,
):
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    desc = f"{arrow2} {text}"
    header = f"**{info} 𑁉 {title}**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_banner(container, banner_url)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_dm_ticket_forwarded_embed(
    settings,
    guild: discord.Guild | None,
    role_name: str,
    reason: str | None,
):
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    reason_text = reason or "—"
    desc = (
        f"{arrow2} Ich habe dein Ticket weitergeleitet, damit dir die richtige Person helfen kann.\n\n"
        f"┏`🎯` - Ziel: **{role_name}**\n"
        f"┗`📝` - Grund: {reason_text}\n\n"
        "Sobald jemand verfügbar ist, meldet sich das Team bei dir."
    )
    header = f"**{info} 𑁉 TICKET WEITERGELEITET**"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{desc}"))
    return _wrap(container)


def build_ticket_log_embed(
    settings,
    guild: discord.Guild | None,
    title: str,
    text: str,
    ticket_id: int,
    thread: discord.Thread | None = None,
    actor: discord.Member | None = None,
):
    info = em(settings, "info", guild) or "ℹ️"
    arrow2 = em(settings, "arrow2", guild) or "»"
    thread_line = f"{thread.mention} ({thread.id})" if thread else "—"
    actor_line = f"{actor.mention} ({actor.id})" if actor else "—"
    desc = (
        f"┏`🎫` - Ticket: `{int(ticket_id)}`\n"
        f"┣`🧵` - Thread: {thread_line}\n"
        f"┣`👤` - Actor: {actor_line}\n"
        f"┗`📝` - Info: {text}"
    )
    header = f"**{info} 𑁉 {title}**"
    body = f"{arrow2} Ticket-Event\n\n{desc}"
    container = discord.ui.Container(accent_colour=_color(settings, guild))
    container.add_item(discord.ui.TextDisplay(f"{header}\n{body}"))
    return _wrap(container)


def build_support_panel_embed(
    settings,
    guild: discord.Guild | None,
    total: int,
    open_: int,
    active: int,
):
    container = build_support_panel_container(settings, guild, total, open_, active)
    return _wrap(container)


def _add_support_panel_banner(container: discord.ui.Container):
    try:
        gallery = discord.ui.MediaGallery()
        gallery.add_item(media=Banners.SUPPORT)
        container.add_item(gallery)
        container.add_item(discord.ui.Separator())
    except Exception:
        pass


def build_support_panel_container(
    settings,
    guild: discord.Guild | None,
    total: int,
    open_: int,
    active: int,
    button: discord.ui.Button | None = None,
):
    arrow2 = em(settings, "arrow2", guild) or "»"
    lifebuoy = em(settings, "lifebuoy", guild) or "🛟"
    sparkles = em(settings, "sparkles", guild) or "✨"
    stats = em(settings, "stats", guild) or "📈"
    info = em(settings, "info", guild) or "ℹ️"
    green = em(settings, "green", guild) or "🟢"
    orange = em(settings, "orange", guild) or "🟠"
    red = em(settings, "red", guild) or "🔴"

    header = f"**{lifebuoy} 𑁉 SUPPORT-PANEL**"
    intro = f"{arrow2} Hilfe in Minuten. Klar, strukturiert und direkt im Server-Design."
    cta = f"{sparkles} **Ticket starten** und dein Anliegen in der DM senden."
    flow = (
        "┏`🎫` - Button klicken\n"
        "┣`📩` - Du bekommst eine DM\n"
        "┣`📝` - Anliegen kurz beschreiben\n"
        "┗`🧵` - Team bearbeitet dein Ticket"
    )
    stats_block = (
        f"┏`📦` - Tickets gesamt: **{total}**\n"
        f"┣{orange} - Offen: **{open_}**\n"
        f"┣{green} - Aktiv (24h): **{active}**\n"
        f"┗{red} - Geschlossen: **{max(0, int(total) - int(open_))}**"
    )
    note_block = (
        f"{info} **Hinweis**\n"
        "Bitte pro Anliegen nur ein Ticket öffnen.\n"
        "Mehr Infos = schnellere Bearbeitung."
    )

    container = discord.ui.Container(accent_colour=_color(settings, guild))
    _add_support_panel_banner(container)
    container.add_item(discord.ui.TextDisplay(f"{header}\n{intro}\n\n{cta}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**So funktioniert es**\n{flow}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(f"**{stats} Live-Stats**\n{stats_block}"))
    container.add_item(discord.ui.Separator())
    container.add_item(discord.ui.TextDisplay(note_block))
    if button:
        container.add_item(discord.ui.Separator())
        row = discord.ui.ActionRow()
        row.add_item(button)
        container.add_item(row)
    return container
