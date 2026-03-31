from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import discord

from bot.modules.debatten.formatting.debatten_embeds import (
    build_archive_embed,
    build_notice_embed,
    build_podium_embed,
    build_signup_review_embed,
    build_topic_review_embed,
    build_topics_embed,
)
from bot.modules.moderation.services.permission_service import PermissionService


BERLIN_TZ = ZoneInfo("Europe/Berlin")
POLITICAL_CORE_TOKENS = {
    "politik",
    "politisch",
    "regierung",
    "regierungen",
    "partei",
    "parteien",
    "wahl",
    "wahlen",
    "demokratie",
    "demokratisch",
    "staat",
    "staaten",
    "parlament",
    "bundestag",
    "bundesrat",
    "kanzler",
    "kanzlerin",
    "präsident",
    "präsidentin",
    "minister",
    "ministerin",
    "ministerpräsident",
    "koalition",
    "opposition",
    "eu",
    "europa",
    "verfassung",
    "gesetz",
    "gesetze",
}
POLITICAL_POLICY_STEMS = (
    "steuer",
    "haushalt",
    "schuldenbremse",
    "migration",
    "asyl",
    "klima",
    "energie",
    "rente",
    "bürgergeld",
    "mindestlohn",
    "inflation",
    "wirtschaft",
    "sozial",
    "bildung",
    "gesundheit",
    "wohnungs",
    "miete",
    "arbeitsmarkt",
    "innenpolitik",
    "außenpolitik",
    "verteidigung",
    "sicherheit",
    "krieg",
    "frieden",
    "digitalisierung",
    "datenschutz",
    "europapolitik",
    "klimapolitik",
    "sozialpolitik",
    "wirtschaftspolitik",
)


async def _ephemeral(
    interaction: discord.Interaction,
    text: str | None = None,
    embed: discord.Embed | None = None,
):
    if embed is None and text is not None:
        settings = getattr(interaction.client, "settings", None)
        if settings:
            embed = build_notice_embed(settings, interaction.guild, text)
            text = None
        else:
            embed = discord.Embed(title="ℹ️ 𑁉 BKT-DEBATTEN", description=text, color=0xB16B91)
            text = None
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=text, embed=embed, ephemeral=True, delete_after=30)
            return
        try:
            await interaction.edit_original_response(content=text, embed=embed)
            return
        except Exception:
            pass
        await interaction.followup.send(content=text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class DebattenService:
    def __init__(self, bot: discord.Client, settings, db, logger):
        self.bot = bot
        self.settings = settings
        self.db = db
        self.logger = logger
        self.permission_service = PermissionService(settings, db)
        self._panel_signatures: dict[int, str] = {}
        self._guild_locks: dict[int, asyncio.Lock] = {}

    def _guild_lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._guild_locks.get(int(guild_id))
        if lock is None:
            lock = asyncio.Lock()
            self._guild_locks[int(guild_id)] = lock
        return lock

    def _clean_text(self, text: str | None) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _normalize_topic_text(self, text: str | None) -> str:
        cleaned = str(text or "").casefold()
        cleaned = cleaned.replace("ß", "ss")
        cleaned = re.sub(r"[^0-9a-zäöü ]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _is_political_topic(self, title: str, description: str) -> bool:
        combined = self._normalize_topic_text(f"{title} {description}")
        if not combined:
            return False
        tokens = set(combined.split())
        if tokens & POLITICAL_CORE_TOKENS:
            return True
        hits = sum(1 for term in POLITICAL_POLICY_STEMS if term in combined)
        return hits >= 2

    def _parse_datetime_input(self, value: str) -> datetime | None:
        raw = self._clean_text(value)
        formats = (
            ("%d.%m.%Y %H:%M", True),
            ("%d.%m.%Y %H.%M", True),
            ("%Y-%m-%d %H:%M", True),
            ("%Y-%m-%d %H.%M", True),
            ("%d.%m.%Y", False),
            ("%Y-%m-%d", False),
        )
        for fmt, has_time in formats:
            try:
                parsed = datetime.strptime(raw, fmt)
            except Exception:
                continue
            if not has_time:
                parsed = parsed.replace(hour=19, minute=0)
            parsed = parsed.replace(tzinfo=BERLIN_TZ)
            return parsed.astimezone(timezone.utc)
        return None

    def _topic_from_row(self, row) -> dict | None:
        if not row:
            return None
        return {
            "id": int(row[0]),
            "guild_id": int(row[1]),
            "title": str(row[2]),
            "description": str(row[3]),
            "status": str(row[4]),
            "submitted_by": int(row[5]),
            "created_via": str(row[6]),
            "reviewed_by": int(row[7]) if row[7] else None,
            "reviewed_at": str(row[8]) if row[8] else None,
            "review_note": str(row[9]) if row[9] else None,
            "created_at": str(row[10]),
        }

    def _decode_speaker_snapshot(self, raw: str | None) -> list[dict]:
        if not raw:
            return []
        try:
            data = json.loads(str(raw))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        out: list[dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                user_id = int(item.get("user_id") or 0)
            except Exception:
                user_id = 0
            name = self._clean_text(str(item.get("name") or ""))
            out.append({"user_id": user_id, "name": name or f"User {user_id}"})
        return out

    def _registration_from_row(self, row) -> dict | None:
        if not row:
            return None
        return {
            "event_id": int(row[0]),
            "guild_id": int(row[1]),
            "user_id": int(row[2]),
            "status": str(row[3] or "pending"),
            "reviewed_by": int(row[4]) if row[4] else None,
            "reviewed_at": str(row[5]) if row[5] else None,
            "review_note": str(row[6]) if row[6] else None,
            "created_at": str(row[7]),
        }

    def _event_from_row(self, row) -> dict | None:
        if not row:
            return None
        return {
            "id": int(row[0]),
            "guild_id": int(row[1]),
            "topic_id": int(row[2]),
            "scheduled_for": str(row[3]),
            "status": str(row[4]),
            "started_at": str(row[5]) if row[5] else None,
            "ended_at": str(row[6]) if row[6] else None,
            "duration_seconds": int(row[7]) if row[7] is not None else None,
            "started_by": int(row[8]) if row[8] else None,
            "ended_by": int(row[9]) if row[9] else None,
            "podium_message_id": int(row[10]) if row[10] else None,
            "stage_channel_id": int(row[11]) if row[11] else None,
            "speaker_snapshot": self._decode_speaker_snapshot(row[12]),
            "created_at": str(row[13]),
            "topic_title": str(row[14]),
            "topic_description": str(row[15]),
        }

    async def _guild_state(self, guild_id: int) -> dict:
        row = await self.db.get_debate_guild(guild_id)
        if not row:
            return {
                "guild_id": int(guild_id),
                "panel_channel_id": 0,
                "panel_message_id": 0,
                "review_channel_id": 0,
                "podium_channel_id": 0,
            }
        return {
            "guild_id": int(row[0]),
            "panel_channel_id": int(row[1] or 0),
            "panel_message_id": int(row[2] or 0),
            "review_channel_id": int(row[3] or 0),
            "podium_channel_id": int(row[4] or 0),
        }

    async def _save_guild_state(self, state: dict):
        await self.db.upsert_debate_guild(
            int(state["guild_id"]),
            int(state.get("panel_channel_id") or 0) or None,
            int(state.get("panel_message_id") or 0) or None,
            int(state.get("review_channel_id") or 0) or None,
            int(state.get("podium_channel_id") or 0) or None,
        )

    async def _get_text_channel(self, guild: discord.Guild, channel_id: int) -> discord.TextChannel | None:
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except Exception:
                channel = None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _get_stage_channel(self, guild: discord.Guild, channel_id: int) -> discord.StageChannel | None:
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except Exception:
                channel = None
        return channel if isinstance(channel, discord.StageChannel) else None

    async def _get_member(self, guild: discord.Guild, user_id: int) -> discord.Member | None:
        member = guild.get_member(int(user_id))
        if member:
            return member
        try:
            return await guild.fetch_member(int(user_id))
        except Exception:
            return None

    def _channel_mention(self, guild: discord.Guild, channel_id: int) -> str:
        if not channel_id:
            return "Nicht gesetzt"
        channel = guild.get_channel(int(channel_id))
        return channel.mention if channel else f"<#{int(channel_id)}>"

    async def _speaker_snapshot_from_members(self, members: list[discord.Member]) -> list[dict]:
        out: list[dict] = []
        seen: set[int] = set()
        for member in members:
            if int(member.id) in seen:
                continue
            seen.add(int(member.id))
            out.append(
                {
                    "user_id": int(member.id),
                    "name": self._clean_text(str(member.display_name or member.name or member.id)),
                }
            )
        return out

    async def _speaker_snapshot_from_registrations(
        self,
        guild: discord.Guild,
        event_id: int,
        *,
        status: str | None = None,
    ) -> list[dict]:
        rows = await self.db.list_debate_registrations(event_id, status=status)
        members: list[discord.Member] = []
        for row in rows or []:
            registration = self._registration_from_row(row)
            user_id = int((registration or {}).get("user_id") or 0)
            if not user_id:
                continue
            member = await self._get_member(guild, user_id)
            if member:
                members.append(member)
        return await self._speaker_snapshot_from_members(members)

    def _preview_names(self, snapshot: list[dict], *, empty_text: str = "Noch niemand angemeldet.") -> str:
        if not snapshot:
            return empty_text
        parts: list[str] = []
        for item in snapshot[:4]:
            name = self._clean_text(str(item.get("name") or "User"))
            user_id = int(item.get("user_id") or 0)
            parts.append(f"<@{user_id}>" if user_id else name)
        if len(snapshot) > 4:
            parts.append(f"+{len(snapshot) - 4}")
        return ", ".join(parts)

    def _merge_members(self, *groups: list[discord.Member]) -> list[discord.Member]:
        merged: list[discord.Member] = []
        seen: set[int] = set()
        for group in groups:
            for member in list(group or []):
                if not isinstance(member, discord.Member):
                    continue
                if int(member.id) in seen:
                    continue
                seen.add(int(member.id))
                merged.append(member)
        return merged

    def _stage_channel_name(self, title: str) -> str:
        clean = self._clean_text(title)
        clean = re.sub(r"[^0-9A-Za-zÄÖÜäöüß \-•]", "", clean).strip()
        if not clean:
            clean = "BKT-Debatte"
        return f"🎙️・{clean[:80]}"

    def _stage_topic(self, title: str) -> str:
        clean = self._clean_text(title)
        return clean[:120] if clean else "BKT-Debatte"

    async def _apply_stage_permissions(self, stage_channel: discord.StageChannel, members: list[discord.Member], *, reason: str):
        for member in members:
            try:
                overwrite = stage_channel.overwrites_for(member)
                overwrite.view_channel = True
                overwrite.connect = True
                overwrite.speak = True
                await stage_channel.set_permissions(member, overwrite=overwrite, reason=reason)
            except Exception:
                continue

    async def _promote_stage_speaker(self, stage_channel: discord.StageChannel, member: discord.Member):
        if not member.voice or not member.voice.channel or int(member.voice.channel.id) != int(stage_channel.id):
            return
        try:
            await member.edit(suppress=False)
        except Exception:
            pass

    async def _promote_stage_speakers(self, stage_channel: discord.StageChannel, members: list[discord.Member]):
        for member in members:
            if member.voice and member.voice.channel and int(member.voice.channel.id) != int(stage_channel.id):
                try:
                    await member.move_to(stage_channel, reason="BKT-Debatte gestartet")
                except Exception:
                    pass
            await self._promote_stage_speaker(stage_channel, member)

    async def _create_stage_channel(
        self,
        guild: discord.Guild,
        podium_channel: discord.TextChannel,
        event: dict,
        speaker_members: list[discord.Member],
    ) -> discord.StageChannel:
        overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=False,
            )
        }
        me = guild.me
        if me:
            overwrites[me] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                manage_channels=True,
                mute_members=True,
                move_members=True,
            )
        for member in speaker_members:
            overwrites[member] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
            )
        stage_channel = await guild.create_stage_channel(
            name=self._stage_channel_name(str(event.get("topic_title") or "")),
            category=podium_channel.category,
            overwrites=overwrites,
            reason=f"BKT-Debatte #{int(event.get('id') or 0)}",
        )
        try:
            await stage_channel.create_instance(
                topic=self._stage_topic(str(event.get("topic_title") or "")),
                privacy_level=discord.PrivacyLevel.guild_only,
                reason=f"BKT-Debatte #{int(event.get('id') or 0)}",
            )
        except Exception:
            try:
                await stage_channel.delete(reason="Stage-Instanz konnte nicht erstellt werden")
            except Exception:
                pass
            raise
        await self._apply_stage_permissions(stage_channel, speaker_members, reason="BKT-Debatte Sprecher bestätigt")
        await self._promote_stage_speakers(stage_channel, speaker_members)
        return stage_channel

    async def _live_stage_speakers(self, guild: discord.Guild, event: dict) -> list[discord.Member]:
        stage_channel = await self._get_stage_channel(guild, int(event.get("stage_channel_id") or 0))
        if not stage_channel:
            return []
        members: list[discord.Member] = []
        for member in list(stage_channel.members or []):
            if member.bot:
                continue
            voice_state = getattr(member, "voice", None)
            if not voice_state or int(getattr(getattr(voice_state, "channel", None), "id", 0) or 0) != int(stage_channel.id):
                continue
            if bool(getattr(voice_state, "suppress", False)):
                continue
            members.append(member)
        return members

    async def _panel_state(self, guild: discord.Guild) -> dict:
        state = await self._guild_state(guild.id)
        next_event = self._event_from_row(await self.db.get_next_planned_debate_event(guild.id))
        live_event = self._event_from_row(await self.db.get_live_debate_event(guild.id))
        next_registration_snapshot: list[dict] = []
        next_registration_count = 0
        next_pending_count = 0
        if next_event:
            next_registration_snapshot = await self._speaker_snapshot_from_registrations(
                guild,
                int(next_event["id"]),
                status="accepted",
            )
            next_registration_count = len(next_registration_snapshot)
            next_pending_count = await self.db.count_debate_registrations(int(next_event["id"]), status="pending")
        return {
            "panel_channel_id": int(state.get("panel_channel_id") or 0),
            "podium_channel_id": int(state.get("podium_channel_id") or 0),
            "next_event": next_event,
            "live_event": live_event,
            "next_registration_count": next_registration_count,
            "next_pending_signup_count": next_pending_count,
            "next_registration_preview": self._preview_names(
                next_registration_snapshot,
                empty_text="Noch keine Sprecher bestätigt.",
            ),
            "pending_topic_count": await self.db.count_debate_topics(guild.id, status="pending"),
            "approved_topic_count": await self.db.count_debate_topics(guild.id, status="approved"),
            "finished_event_count": await self.db.count_debate_events(guild.id, status="finished"),
            "live_speaker_count": len(list((live_event or {}).get("speaker_snapshot") or [])),
            "live_stage_mention": self._channel_mention(guild, int((live_event or {}).get("stage_channel_id") or 0)),
            "podium_mention": self._channel_mention(guild, int(state.get("podium_channel_id") or 0)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _archive_options(self, guild_id: int) -> tuple[list[discord.SelectOption], bool]:
        rows = await self.db.list_recent_finished_debate_events(guild_id, limit=25)
        events = [self._event_from_row(row) for row in rows or [] if row]
        if not events:
            return (
                [
                    discord.SelectOption(
                        label="Noch kein Archiv vorhanden",
                        value="0",
                        description="Abgeschlossene Debatten erscheinen hier.",
                    )
                ],
                True,
            )
        options: list[discord.SelectOption] = []
        for event in events:
            if not event:
                continue
            try:
                dt = datetime.fromisoformat(str(event["scheduled_for"]))
            except Exception:
                dt = None
            date_label = dt.astimezone(BERLIN_TZ).strftime("%d.%m.%Y") if dt else "Archiv"
            speaker_count = len(list(event.get("speaker_snapshot") or []))
            duration = int(event.get("duration_seconds") or 0)
            hours, rest = divmod(duration, 3600)
            minutes = rest // 60
            duration_label = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            options.append(
                discord.SelectOption(
                    label=f"{date_label} • {str(event['topic_title'])[:75]}",
                    value=str(int(event["id"])),
                    description=f"{speaker_count} Sprecher • {duration_label}",
                )
            )
        return options[:25], False

    def _signature_payload(self, state: dict) -> str:
        payload = {
            "next_event": {
                "id": int((state.get("next_event") or {}).get("id") or 0),
                "scheduled_for": str((state.get("next_event") or {}).get("scheduled_for") or ""),
                "title": str((state.get("next_event") or {}).get("topic_title") or ""),
                "registrations": int(state.get("next_registration_count") or 0),
                "pending_signups": int(state.get("next_pending_signup_count") or 0),
                "preview": str(state.get("next_registration_preview") or ""),
            },
            "live_event": {
                "id": int((state.get("live_event") or {}).get("id") or 0),
                "started_at": str((state.get("live_event") or {}).get("started_at") or ""),
                "title": str((state.get("live_event") or {}).get("topic_title") or ""),
                "stage_channel_id": int((state.get("live_event") or {}).get("stage_channel_id") or 0),
                "speakers": list((state.get("live_event") or {}).get("speaker_snapshot") or []),
            },
            "counts": {
                "pending": int(state.get("pending_topic_count") or 0),
                "approved": int(state.get("approved_topic_count") or 0),
                "finished": int(state.get("finished_event_count") or 0),
            },
            "podium": str(state.get("podium_mention") or ""),
            "live_stage": str(state.get("live_stage_mention") or ""),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _is_panel_message(self, message: discord.Message | None) -> bool:
        if not message or not getattr(message, "author", None) or not getattr(self.bot, "user", None):
            return False
        if int(message.author.id) != int(self.bot.user.id):
            return False
        def _walk(items) -> bool:
            for item in list(items or []):
                custom_id = str(getattr(item, "custom_id", "") or "")
                if custom_id.startswith("starry:debatten:"):
                    return True
                if _walk(getattr(item, "children", []) or []):
                    return True
            return False
        try:
            if _walk(message.components or []):
                return True
        except Exception:
            return False
        return False

    async def _find_existing_panel_message(self, target: discord.TextChannel) -> discord.Message | None:
        me = getattr(self.bot, "user", None)
        if not me:
            return None
        try:
            async for message in target.history(limit=30):
                if int(message.author.id) != int(me.id):
                    continue
                if self._is_panel_message(message):
                    return message
        except Exception:
            return None
        return None

    async def _build_panel_view(self, guild_id: int):
        from bot.modules.debatten.views.debatten_panel import DebattenPanelView

        options, disabled = await self._archive_options(guild_id)
        guild = self.bot.get_guild(int(guild_id))
        state = await self._panel_state(guild) if guild else {}
        return DebattenPanelView(
            settings=self.settings,
            guild=guild,
            state=state,
            archive_options=options,
            archive_disabled=disabled,
        )

    async def configure(
        self,
        guild: discord.Guild,
        *,
        panel_channel: discord.TextChannel,
        review_channel: discord.TextChannel,
        podium_channel: discord.TextChannel,
    ):
        state = await self._guild_state(guild.id)
        old_panel_channel_id = int(state.get("panel_channel_id") or 0)
        state["panel_channel_id"] = int(panel_channel.id)
        state["review_channel_id"] = int(review_channel.id)
        state["podium_channel_id"] = int(podium_channel.id)
        if old_panel_channel_id and old_panel_channel_id != int(panel_channel.id):
            state["panel_message_id"] = 0
        await self._save_guild_state(state)
        await self.refresh_panel(guild, force=True)

    async def refresh_panel(self, guild: discord.Guild, *, force: bool = False):
        state = await self._guild_state(guild.id)
        panel_channel = await self._get_text_channel(guild, int(state.get("panel_channel_id") or 0))
        if not panel_channel:
            return
        panel_state = await self._panel_state(guild)
        signature = self._signature_payload(panel_state)
        if not force and self._panel_signatures.get(int(guild.id)) == signature:
            return
        from bot.modules.debatten.views.debatten_panel import DebattenPanelView

        options, disabled = await self._archive_options(guild.id)
        view = DebattenPanelView(
            settings=self.settings,
            guild=guild,
            state=panel_state,
            archive_options=options,
            archive_disabled=disabled,
        )
        message_id = int(state.get("panel_message_id") or 0)
        if message_id:
            try:
                message = await panel_channel.fetch_message(int(message_id))
                await message.edit(view=view, content=None)
                self._panel_signatures[int(guild.id)] = signature
                return
            except Exception:
                state["panel_message_id"] = 0
        reuse = await self._find_existing_panel_message(panel_channel)
        if reuse:
            try:
                await reuse.edit(view=view, content=None)
                state["panel_message_id"] = int(reuse.id)
                await self._save_guild_state(state)
                self._panel_signatures[int(guild.id)] = signature
                return
            except Exception:
                pass
        message = await panel_channel.send(view=view)
        state["panel_message_id"] = int(message.id)
        await self._save_guild_state(state)
        self._panel_signatures[int(guild.id)] = signature

    async def refresh_all_panels(self):
        for guild in list(getattr(self.bot, "guilds", []) or []):
            try:
                await self.refresh_panel(guild)
            except Exception:
                continue

    async def tick(self):
        await self.refresh_all_panels()

    async def _notify_review_channel(
        self,
        guild: discord.Guild,
        embed: discord.Embed,
        *,
        view: discord.ui.View | discord.ui.LayoutView | None = None,
    ):
        state = await self._guild_state(guild.id)
        channel = await self._get_text_channel(guild, int(state.get("review_channel_id") or 0))
        if not channel:
            return
        try:
            await channel.send(embed=embed, view=view)
        except Exception:
            pass

    async def _post_submit_topic(self, guild: discord.Guild, topic_id: int, user_id: int, title: str, description: str):
        try:
            from bot.modules.debatten.views.topic_review import DebattenTopicReviewView

            await self._notify_review_channel(
                guild,
                build_topic_review_embed(
                    self.settings,
                    guild,
                    {
                        "topic_id": topic_id,
                        "title": title,
                        "description": description,
                        "status_label": "Offen",
                        "user_id": user_id,
                        "source_label": "Panel",
                    },
                ),
                view=DebattenTopicReviewView(int(topic_id)),
            )
        except Exception:
            pass
        try:
            await self.refresh_panel(guild, force=True)
        except Exception:
            pass

    async def submit_topic(self, interaction: discord.Interaction, *, title: str, description: str):
        if not interaction.guild or not interaction.user:
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        clean_title = self._clean_text(title)
        clean_description = self._clean_text(description)
        if len(clean_title) < 8:
            return await _ephemeral(interaction, "Bitte gib ein etwas klareres Thema an.")
        if len(clean_description) < 20:
            return await _ephemeral(interaction, "Bitte beschreibe das Thema etwas ausführlicher.")
        await _ephemeral(interaction, "Thema wird eingereicht …")
        topic_id = await self.db.create_debate_topic(
            interaction.guild.id,
            clean_title,
            clean_description,
            int(interaction.user.id),
            status="pending",
            created_via="panel",
        )
        await _ephemeral(
            interaction,
            f"Dein Thema wurde eingereicht. Themen-ID: `#{topic_id}`. Bitte reiche weiterhin nur politische Debattenthemen ein.",
        )
        asyncio.create_task(
            self._post_submit_topic(
                interaction.guild,
                int(topic_id),
                int(interaction.user.id),
                clean_title,
                clean_description,
            )
        )

    async def create_official_topic(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        *,
        title: str,
        description: str,
    ) -> int:
        clean_title = self._clean_text(title)
        clean_description = self._clean_text(description)
        topic_id = await self.db.create_debate_topic(
            guild.id,
            clean_title,
            clean_description,
            int(actor.id),
            status="approved",
            created_via="command",
            reviewed_by=int(actor.id),
            review_note="Direkt als bestätigtes Thema angelegt.",
        )
        await self._notify_review_channel(
            guild,
            build_topic_review_embed(
                self.settings,
                guild,
                {
                    "topic_id": topic_id,
                    "title": clean_title,
                    "description": clean_description,
                    "status_label": "Bestätigt",
                    "user_id": int(actor.id),
                    "source_label": "Befehl",
                    "review_note": "Direkt als bestätigtes Thema angelegt.",
                },
            ),
        )
        await self.refresh_panel(guild, force=True)
        return topic_id

    async def set_topic_status(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        *,
        topic_id: int,
        status: str,
        review_note: str | None = None,
        announce: bool = True,
    ) -> tuple[bool, str]:
        topic = self._topic_from_row(await self.db.get_debate_topic(topic_id))
        if not topic or int(topic["guild_id"]) != int(guild.id):
            return False, "Thema nicht gefunden."
        if str(topic["status"]) == str(status):
            return False, "Dieser Status ist bereits gesetzt."
        await self.db.set_debate_topic_status(
            int(topic_id),
            str(status),
            reviewed_by=int(actor.id),
            review_note=review_note,
        )
        label = "Bestätigt" if status == "approved" else "Abgelehnt"
        if announce:
            await self._notify_review_channel(
                guild,
                build_topic_review_embed(
                    self.settings,
                    guild,
                    {
                        "topic_id": int(topic["id"]),
                        "title": topic["title"],
                        "description": topic["description"],
                        "status_label": label,
                        "user_id": int(topic["submitted_by"]),
                        "source_label": "Review",
                        "review_note": review_note,
                    },
                ),
            )
        await self.refresh_panel(guild, force=True)
        return True, f"Thema `#{int(topic['id'])}` wurde auf **{label}** gesetzt."

    async def list_topics_embed(self, guild: discord.Guild, *, status: str | None = None) -> discord.Embed:
        rows = await self.db.list_debate_topics(guild.id, status=status, limit=25)
        mapped = [self._topic_from_row(row) for row in rows or [] if row]
        title = "🧠 𑁉 DEBATTEN-THEMEN"
        if status:
            title += f" • {status.upper()}"
        return build_topics_embed(self.settings, guild, mapped, title=title)

    async def plan_debate(self, guild: discord.Guild, actor: discord.Member, *, topic_id: int, scheduled_for_raw: str) -> tuple[bool, str]:
        topic = self._topic_from_row(await self.db.get_debate_topic(topic_id))
        if not topic or int(topic["guild_id"]) != int(guild.id):
            return False, "Thema nicht gefunden."
        if str(topic["status"]) != "approved":
            return False, "Nur bestätigte Themen können geplant werden."
        scheduled_for = self._parse_datetime_input(scheduled_for_raw)
        if not scheduled_for:
            return False, "Datum ungültig. Nutze z. B. `30.03.2026 19:30`."
        if scheduled_for <= datetime.now(timezone.utc):
            return False, "Bitte plane die Debatte in der Zukunft."
        event_id = await self.db.create_debate_event(
            guild.id,
            int(topic["id"]),
            scheduled_for.isoformat(),
        )
        await self.refresh_panel(guild, force=True)
        return True, f"Debatte `#{event_id}` für **{topic['title']}** wurde geplant."

    async def toggle_signup(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        await _ephemeral(interaction, "Anmeldung wird aktualisiert …")
        async with self._guild_lock(interaction.guild.id):
            event = self._event_from_row(await self.db.get_next_planned_debate_event(interaction.guild.id))
            if not event:
                return await _ephemeral(interaction, "Aktuell ist noch keine nächste Debatte geplant.")
            existing = self._registration_from_row(
                await self.db.get_debate_registration(int(event["id"]), int(interaction.user.id))
            )
            joined = not bool(existing)
            if joined:
                await self.db.create_debate_registration(int(event["id"]), interaction.guild.id, int(interaction.user.id))
            else:
                await self.db.remove_debate_registration(int(event["id"]), int(interaction.user.id))
        await self._notify_review_channel(
            interaction.guild,
            build_signup_review_embed(
                self.settings,
                interaction.guild,
                {
                    "joined": joined,
                    "status_label": "Offen" if joined else "Entfernt",
                    "display_name": interaction.user.display_name,
                    "user_id": int(interaction.user.id),
                    "topic_title": event["topic_title"],
                    "scheduled_for": event["scheduled_for"],
                    "event_id": int(event["id"]),
                },
            ),
        )
        await self.refresh_panel(interaction.guild, force=True)
        if joined:
            return await _ephemeral(interaction, f"Du bist jetzt für **{event['topic_title']}** angemeldet.")
        return await _ephemeral(interaction, f"Deine Anmeldung für **{event['topic_title']}** wurde entfernt.")

    async def set_signup_status(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        *,
        event_id: int,
        member: discord.Member,
        status: str,
        review_note: str | None = None,
    ) -> tuple[bool, str]:
        event = self._event_from_row(await self.db.get_debate_event(event_id))
        if not event or int(event["guild_id"]) != int(guild.id):
            return False, "Debatte nicht gefunden."
        registration = self._registration_from_row(await self.db.get_debate_registration(int(event_id), int(member.id)))
        if not registration:
            return False, "Für diesen User liegt keine Anmeldung vor."
        if str(registration.get("status") or "pending") == str(status):
            return False, "Dieser Anmeldestatus ist bereits gesetzt."
        updated = await self.db.set_debate_registration_status(
            int(event_id),
            int(member.id),
            str(status),
            reviewed_by=int(actor.id),
            review_note=review_note,
        )
        if updated <= 0:
            return False, "Die Anmeldung konnte nicht aktualisiert werden."
        status_label = "Angenommen" if status == "accepted" else "Abgelehnt"
        await self._notify_review_channel(
            guild,
            build_signup_review_embed(
                self.settings,
                guild,
                {
                    "joined": True,
                    "status_label": status_label,
                    "display_name": member.display_name,
                    "user_id": int(member.id),
                    "topic_title": event["topic_title"],
                    "scheduled_for": event["scheduled_for"],
                    "event_id": int(event["id"]),
                    "review_note": review_note,
                    "reviewed_by": int(actor.id),
                },
            ),
        )
        live_event = self._event_from_row(await self.db.get_live_debate_event(guild.id))
        if status == "accepted" and live_event and int(live_event["id"]) == int(event_id):
            stage_channel = await self._get_stage_channel(guild, int(live_event.get("stage_channel_id") or 0))
            if stage_channel:
                await self._apply_stage_permissions(stage_channel, [member], reason="BKT-Debatte Sprecher angenommen")
                await self._promote_stage_speaker(stage_channel, member)
        await self.refresh_panel(guild, force=True)
        return True, f"Anmeldung von {member.mention} für Debatte `#{int(event['id'])}` wurde auf **{status_label}** gesetzt."

    async def start_debate(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        *,
        event_id: int | None = None,
        speakers: list[discord.Member] | None = None,
    ) -> tuple[bool, str]:
        async with self._guild_lock(guild.id):
            live = self._event_from_row(await self.db.get_live_debate_event(guild.id))
            if live:
                return False, "Es läuft bereits eine Debatte."
            row = await self.db.get_debate_event(event_id) if event_id else await self.db.get_next_planned_debate_event(guild.id)
            event = self._event_from_row(row)
            if not event or int(event["guild_id"]) != int(guild.id):
                return False, "Keine passende geplante Debatte gefunden."
            if str(event["status"]) != "planned":
                return False, "Diese Debatte ist nicht mehr im Status `planned`."
            state = await self._guild_state(guild.id)
            podium_channel = await self._get_text_channel(guild, int(state.get("podium_channel_id") or 0))
            if not podium_channel:
                return False, "Kein Podium-Channel konfiguriert."
            approved_rows = await self.db.list_debate_registrations(int(event["id"]), status="accepted")
            approved_members: list[discord.Member] = []
            for row in approved_rows or []:
                registration = self._registration_from_row(row)
                user_id = int((registration or {}).get("user_id") or 0)
                if not user_id:
                    continue
                member = await self._get_member(guild, user_id)
                if member:
                    approved_members.append(member)
            manual_members = [member for member in list(speakers or []) if isinstance(member, discord.Member)]
            speaker_members = self._merge_members(approved_members, manual_members)
            if not speaker_members:
                return False, "Es wurden noch keine Sprecher angenommen. Bestätige erst Anmeldungen oder gib Sprecher direkt mit an."
            speaker_snapshot = await self._speaker_snapshot_from_members(speaker_members)
            started_at = datetime.now(timezone.utc).isoformat()
            event["started_at"] = started_at
            event["speaker_snapshot"] = speaker_snapshot
            try:
                stage_channel = await self._create_stage_channel(guild, podium_channel, event, speaker_members)
            except Exception:
                return False, "Die Stage für die Debatte konnte nicht erstellt werden."
            event["stage_channel_id"] = int(stage_channel.id)
            try:
                message = await podium_channel.send(embed=build_podium_embed(self.settings, guild, event, live=True))
            except Exception:
                try:
                    await stage_channel.delete(reason="Debatten-Start abgebrochen")
                except Exception:
                    pass
                return False, "Die Debatten-Nachricht im Podium konnte nicht gesendet werden."
            await self.db.mark_debate_event_live(
                int(event["id"]),
                int(actor.id),
                started_at,
                int(message.id),
                int(stage_channel.id),
                json.dumps(speaker_snapshot, ensure_ascii=False),
            )
        await self.refresh_panel(guild, force=True)
        return True, f"Debatte `#{int(event['id'])}` wurde gestartet. Stage: {self._channel_mention(guild, int(event.get('stage_channel_id') or 0))}"

    async def end_debate(self, guild: discord.Guild, actor: discord.Member) -> tuple[bool, str]:
        async with self._guild_lock(guild.id):
            event = self._event_from_row(await self.db.get_live_debate_event(guild.id))
            if not event:
                return False, "Es läuft gerade keine Debatte."
            started_at = datetime.fromisoformat(str(event["started_at"])) if event.get("started_at") else datetime.now(timezone.utc)
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            ended_at_dt = datetime.now(timezone.utc)
            duration_seconds = max(0, int((ended_at_dt - started_at).total_seconds()))
            ended_at = ended_at_dt.isoformat()
            live_speakers = await self._live_stage_speakers(guild, event)
            if live_speakers:
                event["speaker_snapshot"] = await self._speaker_snapshot_from_members(live_speakers)
            await self.db.finish_debate_event(
                int(event["id"]),
                int(actor.id),
                ended_at,
                duration_seconds,
                json.dumps(list(event.get("speaker_snapshot") or []), ensure_ascii=False),
            )
            event["ended_at"] = ended_at
            event["duration_seconds"] = duration_seconds
            state = await self._guild_state(guild.id)
            podium_channel = await self._get_text_channel(guild, int(state.get("podium_channel_id") or 0))
            if podium_channel and int(event.get("podium_message_id") or 0):
                try:
                    message = await podium_channel.fetch_message(int(event["podium_message_id"]))
                    await message.edit(embed=build_podium_embed(self.settings, guild, event, live=False))
                except Exception:
                    pass
            stage_channel = await self._get_stage_channel(guild, int(event.get("stage_channel_id") or 0))
            if stage_channel:
                try:
                    await stage_channel.delete(reason=f"BKT-Debatte #{int(event['id'])} beendet")
                except Exception:
                    pass
        await self.refresh_panel(guild, force=True)
        return True, f"Debatte `#{int(event['id'])}` wurde beendet."

    async def handle_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        if member.bot or not member.guild:
            return
        stage_channel = after.channel if isinstance(after.channel, discord.StageChannel) else None
        if not stage_channel:
            return
        event = self._event_from_row(await self.db.get_live_debate_event(member.guild.id))
        if not event:
            return
        if int(event.get("stage_channel_id") or 0) != int(stage_channel.id):
            return
        speaker_ids = {int(item.get("user_id") or 0) for item in list(event.get("speaker_snapshot") or [])}
        if int(member.id) not in speaker_ids:
            return
        await self._apply_stage_permissions(stage_channel, [member], reason="BKT-Debatte Sprecher beigetreten")
        await self._promote_stage_speaker(stage_channel, member)

    async def archive_embed(self, guild: discord.Guild | None, event_id: int) -> discord.Embed:
        if not guild:
            return build_notice_embed(self.settings, None, "Nur im Server nutzbar.")
        event = self._event_from_row(await self.db.get_debate_event(event_id))
        if not event or int(event["guild_id"]) != int(guild.id):
            return build_notice_embed(self.settings, guild, "Archiv-Eintrag nicht gefunden.")
        return build_archive_embed(self.settings, guild, event)
