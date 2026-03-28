from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

import discord

from bot.modules.emoji_quiz.data.question_bank import (
    EMOJI_QUIZ_BANK,
    EMOJI_QUIZ_CATEGORY_ALIASES,
    EMOJI_QUIZ_CATEGORY_ORDER,
)
from bot.modules.emoji_quiz.formatting.emoji_quiz_embeds import (
    build_closed_embed,
    build_dashboard_view,
    build_hint_embed,
    build_notice_embed,
    build_result_embed,
    build_round_embed,
    build_stats_embed,
    build_submission_view,
)
from bot.modules.moderation.services.permission_service import PermissionService


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
            embed = discord.Embed(title="ℹ️ 𑁉 EMOJI-QUIZ", description=text, color=0xB16B91)
            text = None
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(content=text, embed=embed, ephemeral=True, delete_after=30)
        else:
            await interaction.followup.send(content=text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


@dataclass
class ActiveEmojiRound:
    guild_id: int
    target_channel_id: int
    target_thread_id: int
    prompt_message_id: int
    category_key: str
    category_label: str
    prompt: str
    answer: str
    aliases: set[str]
    round_number: int
    started_by: int | None
    auto_started: bool
    end_at: datetime
    timeout_task: asyncio.Task | None = None
    hint_task: asyncio.Task | None = None
    attempts: int = 0


class EmojiQuestionSubmitModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="📥 Emoji-Quiz-Frage einreichen")
        self.service = service
        self.category = discord.ui.TextInput(
            label="Kategorie",
            style=discord.TextStyle.short,
            max_length=60,
            required=True,
            placeholder="z. B. Filme, Städte, Märchen",
        )
        self.prompt = discord.ui.TextInput(
            label="Emoji-Frage",
            style=discord.TextStyle.short,
            max_length=120,
            required=True,
            placeholder="z. B. 🦁👑",
        )
        self.answer = discord.ui.TextInput(
            label="Antwort",
            style=discord.TextStyle.short,
            max_length=120,
            required=True,
            placeholder="z. B. Der König der Löwen",
        )
        self.aliases = discord.ui.TextInput(
            label="Zusätzliche Antworten",
            style=discord.TextStyle.paragraph,
            max_length=250,
            required=False,
            placeholder="Optional, getrennt mit Komma oder Zeilenumbruch",
        )
        self.add_item(self.category)
        self.add_item(self.prompt)
        self.add_item(self.answer)
        self.add_item(self.aliases)

    async def on_submit(self, interaction: discord.Interaction):
        await self.service.submit_question(
            interaction,
            category_raw=str(self.category.value),
            prompt=str(self.prompt.value),
            answer=str(self.answer.value),
            aliases_raw=str(self.aliases.value or ""),
        )


class EmojiCategorySubmitModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="🗂️ Emoji-Kategorie einreichen")
        self.service = service
        self.label = discord.ui.TextInput(
            label="Kategoriename",
            style=discord.TextStyle.short,
            max_length=50,
            required=True,
            placeholder="z. B. Fußballer, Anime, Starry-Insider",
        )
        self.description = discord.ui.TextInput(
            label="Beschreibung",
            style=discord.TextStyle.paragraph,
            max_length=300,
            required=True,
            placeholder="Kurz erklären, welche Rätsel dort vorkommen sollen",
        )
        self.add_item(self.label)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        await self.service.submit_category(
            interaction,
            label=str(self.label.value),
            description=str(self.description.value),
        )


class EmojiUserSubmitModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="👤 User-Emoji einreichen")
        self.service = service
        self.prompt = discord.ui.TextInput(
            label="Deine Emoji-Beschreibung",
            style=discord.TextStyle.short,
            max_length=120,
            required=True,
            placeholder="z. B. ☕🎮🧠🌙",
        )
        self.aliases = discord.ui.TextInput(
            label="Zusätzliche Namens-Aliase",
            style=discord.TextStyle.paragraph,
            max_length=250,
            required=False,
            placeholder="Optional, z. B. alter Nickname oder Kurzform",
        )
        self.add_item(self.prompt)
        self.add_item(self.aliases)

    async def on_submit(self, interaction: discord.Interaction):
        await self.service.submit_user_question(
            interaction,
            prompt=str(self.prompt.value),
            aliases_raw=str(self.aliases.value or ""),
        )


class EmojiQuizService:
    TRANSIENT_MESSAGE_DELETE_AFTER = 20
    ANSWER_MESSAGE_DELETE_AFTER = 6

    def __init__(self, bot: discord.Client, settings, db, logger):
        self.bot = bot
        self.settings = settings
        self.db = db
        self.logger = logger
        self.permission_service = PermissionService(settings, db)
        self._rounds: dict[int, ActiveEmojiRound] = {}
        self._resolve_locks: dict[int, asyncio.Lock] = {}
        self._next_auto_at: dict[int, datetime] = {}
        self._recent_answers: dict[int, list[str]] = {}

    def _enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "emoji_quiz.enabled", True))

    def _default_timeout_seconds(self, guild_id: int) -> int:
        return max(20, int(self.settings.get_guild_int(guild_id, "emoji_quiz.round_timeout_seconds", 240) or 240))

    def _default_auto_interval_seconds(self, guild_id: int) -> int:
        return max(30, int(self.settings.get_guild_int(guild_id, "emoji_quiz.auto_interval_seconds", 240) or 240))

    def _points_per_win(self, guild_id: int) -> int:
        return max(1, int(self.settings.get_guild_int(guild_id, "emoji_quiz.points_per_win", 10) or 10))

    def _reveal_hints_enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "emoji_quiz.reveal_hints", True))

    def _first_hint_after_seconds(self, guild_id: int) -> int:
        return max(20, int(self.settings.get_guild_int(guild_id, "emoji_quiz.first_hint_after_seconds", 90) or 90))

    def _second_hint_after_seconds(self, guild_id: int) -> int:
        return max(30, int(self.settings.get_guild_int(guild_id, "emoji_quiz.second_hint_after_seconds", 170) or 170))

    def _review_forum_channel_id(self, guild_id: int) -> int:
        return max(0, int(self.settings.get_guild_int(guild_id, "emoji_quiz.review_forum_channel_id", 0) or 0))

    def _period_keys(self, now: datetime | None = None) -> tuple[str, str]:
        stamp = now or datetime.now(timezone.utc)
        iso = stamp.isocalendar()
        return f"{int(iso.year):04d}-W{int(iso.week):02d}", f"{int(stamp.year):04d}-{int(stamp.month):02d}"

    def current_period_keys(self) -> tuple[str, str]:
        return self._period_keys()

    def _apply_period_rollover(self, stats: dict[str, Any], now: datetime | None = None):
        week_key, month_key = self._period_keys(now)
        if str(stats.get("weekly_key") or "") != week_key:
            stats["weekly_key"] = week_key
            stats["weekly_points"] = 0
        if str(stats.get("monthly_key") or "") != month_key:
            stats["monthly_key"] = month_key
            stats["monthly_points"] = 0

    def _normalize(self, text: str) -> str:
        out = str(text or "").casefold().strip()
        out = out.replace("ß", "ss")
        out = re.sub(r"[^0-9a-zäöü ]", " ", out)
        out = re.sub(r"\s+", " ", out).strip()
        return out

    def _fuzzy_match(self, text: str, candidate: str) -> bool:
        left = self._normalize(text)
        right = self._normalize(candidate)
        if not left or not right:
            return False
        if left == right:
            return True
        if abs(len(left) - len(right)) > 3:
            return False
        ratio = SequenceMatcher(None, left, right).ratio()
        return ratio >= 0.82 if len(right) <= 8 else ratio >= 0.76

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "")).strip()

    def _masked_answer(self, answer: str, stage: int) -> str:
        text = self._clean_text(answer)
        if not text:
            return "—"
        parts = re.split(r"(\s+)", text)
        out: list[str] = []
        for part in parts:
            if not part or part.isspace():
                out.append(part)
                continue
            letter_indexes = [idx for idx, ch in enumerate(part) if ch.isalnum()]
            if not letter_indexes:
                out.append(part)
                continue
            if stage <= 1:
                reveal_count = 1
            else:
                reveal_count = max(2, min(len(letter_indexes), (len(letter_indexes) + 1) // 2))
            visible = set(letter_indexes[:reveal_count])
            out.append("".join(ch if (idx in visible or not ch.isalnum()) else "•" for idx, ch in enumerate(part)))
        return "".join(out)

    async def _run_hint_sequence(self, guild: discord.Guild, round_: ActiveEmojiRound):
        if not self._reveal_hints_enabled(guild.id):
            return
        checkpoints = [
            (self._first_hint_after_seconds(guild.id), 1),
            (self._second_hint_after_seconds(guild.id), 2),
        ]
        sent_after = 0
        for after_seconds, stage in checkpoints:
            if after_seconds <= sent_after:
                continue
            wait_seconds = max(1, after_seconds - sent_after)
            sent_after = after_seconds
            try:
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                return
            current = self._rounds.get(guild.id)
            if current is not round_:
                return
            target = await self._resolve_target(guild, round_.target_channel_id, round_.target_thread_id)
            if not isinstance(target, (discord.TextChannel, discord.Thread)):
                return
            try:
                await target.send(
                    embed=build_hint_embed(
                        self.settings,
                        guild,
                        round_.category_label,
                        self._masked_answer(round_.answer, stage),
                        stage,
                    ),
                    delete_after=self.TRANSIENT_MESSAGE_DELETE_AFTER,
                )
            except Exception:
                return

    def _canonical_category_key(self, key: str | None) -> str:
        raw = self._clean_text(key or "").lower()
        return str(EMOJI_QUIZ_CATEGORY_ALIASES.get(raw, raw))

    def _default_category_keys(self, guild_id: int) -> list[str]:
        raw = self.settings.get_guild(guild_id, "emoji_quiz.enabled_categories", EMOJI_QUIZ_CATEGORY_ORDER) or EMOJI_QUIZ_CATEGORY_ORDER
        if not isinstance(raw, list):
            raw = list(EMOJI_QUIZ_CATEGORY_ORDER)
        return [self._canonical_category_key(str(key)) for key in raw if str(key).strip()]

    def _parse_aliases(self, raw: str | None) -> list[str]:
        if not raw:
            return []
        parts = re.split(r"[,;\n]+", str(raw))
        out: list[str] = []
        seen: set[str] = set()
        for part in parts:
            value = self._clean_text(part)
            if not value:
                continue
            norm = self._normalize(value)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            out.append(value)
        return out

    def _dedupe_aliases(self, values: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            clean = self._clean_text(value)
            if not clean:
                continue
            norm = self._normalize(clean)
            if not norm or norm in seen:
                continue
            seen.add(norm)
            out.append(clean)
        return out

    def _slugify_category_key(self, label: str) -> str:
        key = str(label or "").strip().lower()
        key = re.sub(r"[^0-9a-zäöüß]+", "_", key)
        key = re.sub(r"_+", "_", key).strip("_")
        return key[:40] or "community"

    def _submission_type_label(self, submission_type: str) -> str:
        return {
            "question": "Frage",
            "category": "Kategorie",
            "user_question": "User-Frage",
        }.get(str(submission_type), "Einreichung")

    def _submission_thread_name(self, user: discord.abc.User, submission_type: str, submission_id: int | None = None) -> str:
        base = str(getattr(user, "display_name", None) or getattr(user, "global_name", None) or user.name or "User").replace("#", "").strip()
        prefix = f"📥 {self._submission_type_label(submission_type)}"
        return (f"{prefix} #{int(submission_id)} · {base}" if submission_id else f"{prefix} · {base}")[:100]

    def _status_tag_name(self, status: str) -> str:
        value = str(status or "pending").lower()
        if value == "accepted":
            return "✅ ANGENOMMEN"
        if value == "rejected":
            return "⛔ ABGELEHNT"
        return "⏳ ERWARTET"

    def _status_tag_names(self) -> set[str]:
        return {self._status_tag_name("pending").lower(), self._status_tag_name("accepted").lower(), self._status_tag_name("rejected").lower()}

    def _category_payload(self, key: str, payload: dict, *, custom: bool = False) -> dict[str, Any]:
        description = str(payload.get("description") or "").strip() or f"{payload.get('label', key)}-Rätsel"
        return {
            "key": str(key),
            "label": str(payload.get("label") or key),
            "emoji": str(payload.get("emoji") or ("🧩" if custom else "🎲")),
            "description": description,
            "custom": bool(custom),
        }

    async def _base_category_catalog(self, guild_id: int) -> dict[str, dict[str, Any]]:
        catalog: dict[str, dict[str, Any]] = {}
        for key in EMOJI_QUIZ_CATEGORY_ORDER:
            payload = EMOJI_QUIZ_BANK.get(str(key))
            if payload:
                catalog[str(key)] = self._category_payload(str(key), payload, custom=False)
        custom_rows = await self.db.list_emoji_quiz_custom_categories(int(guild_id), active_only=True)
        for row in custom_rows:
            key = str(row[1] or "").strip()
            if not key or key in catalog:
                continue
            catalog[key] = self._category_payload(
                key,
                {"label": str(row[2] or key), "emoji": "🧩", "description": str(row[3] or "Community-Kategorie")},
                custom=True,
            )
        return catalog

    def _ordered_category_keys(self, catalog: dict[str, dict[str, Any]]) -> list[str]:
        ordered = [key for key in EMOJI_QUIZ_CATEGORY_ORDER if key in catalog]
        extras = sorted(
            [key for key in catalog if key not in EMOJI_QUIZ_CATEGORY_ORDER],
            key=lambda key: (self._normalize(str(catalog[key].get("label") or key)), key),
        )
        return ordered + extras

    def _match_category_key(self, catalog: dict[str, dict[str, Any]], raw: str | None) -> str | None:
        value = self._clean_text(raw or "")
        if not value:
            return None
        lower = self._canonical_category_key(value.lower())
        if lower in catalog:
            return lower
        slug = self._slugify_category_key(value)
        if slug in catalog:
            return slug
        norm = self._normalize(value)
        for key, payload in catalog.items():
            if norm == self._normalize(key) or norm == self._normalize(str(payload.get("label") or key)):
                return key
        for key, payload in catalog.items():
            hay = " ".join([key, str(payload.get("label") or key), str(payload.get("description") or "")])
            if norm and norm in self._normalize(hay):
                return key
        return None

    async def resolve_category_key(self, guild_id: int, raw: str | None, enabled_only: bool = False) -> str | None:
        catalog = await self._base_category_catalog(guild_id)
        if enabled_only:
            state = await self._guild_state(guild_id)
            enabled = {str(key) for key in state["enabled_categories"]}
            catalog = {key: payload for key, payload in catalog.items() if key in enabled}
        return self._match_category_key(catalog, raw)

    async def _clean_category_inputs(self, guild_id: int, values: list[str] | None) -> list[str]:
        if not values:
            return []
        catalog = await self._base_category_catalog(guild_id)
        out: list[str] = []
        seen: set[str] = set()
        for value in values:
            key = self._match_category_key(catalog, value)
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    async def _guild_state(self, guild_id: int) -> dict[str, Any]:
        row = await self.db.get_emoji_quiz_guild(int(guild_id))
        catalog = await self._base_category_catalog(guild_id)
        default_categories = [key for key in self._default_category_keys(guild_id) if key in catalog]
        if not default_categories:
            default_categories = self._ordered_category_keys(catalog)
        defaults = {
            "guild_id": int(guild_id),
            "target_channel_id": 0,
            "target_thread_id": 0,
            "panel_message_id": 0,
            "auto_enabled": False,
            "auto_interval_seconds": self._default_auto_interval_seconds(guild_id),
            "round_timeout_seconds": self._default_timeout_seconds(guild_id),
            "enabled_categories": default_categories,
            "rounds_total": 0,
            "last_winner_id": 0,
        }
        if not row:
            return defaults
        try:
            categories = json.loads(str(row[7])) if row[7] else defaults["enabled_categories"]
        except Exception:
            categories = defaults["enabled_categories"]
        categories = [self._canonical_category_key(str(key)) for key in categories if self._canonical_category_key(str(key)) in catalog]
        if not categories:
            categories = list(default_categories)
        return {
            "guild_id": int(row[0]),
            "target_channel_id": int(row[1] or 0),
            "target_thread_id": int(row[2] or 0),
            "panel_message_id": int(row[3] or 0),
            "auto_enabled": bool(int(row[4] or 0)),
            "auto_interval_seconds": int(row[5] or defaults["auto_interval_seconds"]),
            "round_timeout_seconds": int(row[6] or defaults["round_timeout_seconds"]),
            "enabled_categories": categories,
            "rounds_total": int(row[8] or 0),
            "last_winner_id": int(row[9] or 0),
        }

    async def _save_guild_state(self, state: dict[str, Any]):
        await self.db.upsert_emoji_quiz_guild(
            int(state["guild_id"]),
            int(state.get("target_channel_id") or 0) or None,
            int(state.get("target_thread_id") or 0) or None,
            int(state.get("panel_message_id") or 0) or None,
            bool(state.get("auto_enabled")),
            int(state.get("auto_interval_seconds") or 240),
            int(state.get("round_timeout_seconds") or 240),
            json.dumps(list(state.get("enabled_categories") or []), ensure_ascii=False),
            int(state.get("rounds_total") or 0),
            int(state.get("last_winner_id") or 0) or None,
        )

    async def _ensure_category_enabled(self, guild_id: int, key: str):
        catalog = await self._base_category_catalog(guild_id)
        if key not in catalog:
            return
        state = await self._guild_state(guild_id)
        if key in state["enabled_categories"]:
            return
        enabled = list(state["enabled_categories"]) + [key]
        state["enabled_categories"] = [candidate for candidate in self._ordered_category_keys(catalog) if candidate in enabled]
        await self._save_guild_state(state)

    async def _question_pool_map(self, guild_id: int) -> dict[str, list[dict[str, Any]]]:
        pool: dict[str, list[dict[str, Any]]] = {
            str(key): [dict(item) for item in list(payload.get("items") or [])]
            for key, payload in EMOJI_QUIZ_BANK.items()
        }
        rows = await self.db.list_emoji_quiz_custom_questions(int(guild_id), category_key=None, active_only=True)
        for row in rows:
            category_key = self._canonical_category_key(str(row[2] or "").strip())
            if not category_key:
                continue
            try:
                aliases = json.loads(str(row[5] or "[]")) if row[5] else []
            except Exception:
                aliases = []
            pool.setdefault(category_key, []).append(
                {
                    "prompt": str(row[3] or ""),
                    "answer": str(row[4] or ""),
                    "aliases": list(aliases or []),
                    "subject_user_id": int(row[8]) if row[8] else None,
                }
            )
        return pool

    async def category_catalog(self, guild_id: int, enabled_only: bool = False) -> list[dict[str, Any]]:
        catalog = await self._base_category_catalog(guild_id)
        pool = await self._question_pool_map(guild_id)
        if enabled_only:
            state = await self._guild_state(guild_id)
            keys = [key for key in state["enabled_categories"] if key in catalog]
        else:
            keys = self._ordered_category_keys(catalog)
        return [{**catalog[key], "question_count": len(pool.get(key, []))} for key in keys if key in catalog]

    async def category_select_options(self, guild_id: int) -> list[discord.SelectOption]:
        options: list[discord.SelectOption] = []
        for payload in await self.category_catalog(guild_id, enabled_only=True):
            options.append(
                discord.SelectOption(
                    label=str(payload["label"]),
                    value=str(payload["key"]),
                    emoji=str(payload["emoji"]),
                    description=f"{int(payload['question_count'])} Rätsel",
                )
            )
        return options[:25]

    async def autocomplete_category_choices(self, guild_id: int, current: str, enabled_only: bool = False) -> list[tuple[str, str]]:
        term = self._normalize(current or "")
        out: list[tuple[str, str]] = []
        for payload in await self.category_catalog(guild_id, enabled_only=enabled_only):
            hay = " ".join([str(payload["key"]), str(payload["label"]), str(payload.get("description") or "")])
            if term and term not in self._normalize(hay):
                continue
            out.append((str(payload["key"]), f"{payload['emoji']} {payload['label']} ({int(payload['question_count'])})"))
        return out[:25]

    async def _get_player_stats(self, guild_id: int, user_id: int) -> dict[str, Any]:
        row = await self.db.get_emoji_quiz_player_stats(int(guild_id), int(user_id))
        week_key, month_key = self._period_keys()
        if not row:
            return {
                "total_points": 0,
                "weekly_points": 0,
                "weekly_key": week_key,
                "monthly_points": 0,
                "monthly_key": month_key,
                "correct": 0,
                "attempts": 0,
                "rounds_started": 0,
                "rounds_closed": 0,
                "current_streak": 0,
                "best_streak": 0,
            }
        stats = {
            "total_points": int(row[2] or 0),
            "weekly_points": int(row[3] or 0),
            "weekly_key": str(row[4] or ""),
            "monthly_points": int(row[5] or 0),
            "monthly_key": str(row[6] or ""),
            "correct": int(row[7] or 0),
            "attempts": int(row[8] or 0),
            "rounds_started": int(row[9] or 0),
            "rounds_closed": int(row[10] or 0),
            "current_streak": int(row[11] or 0),
            "best_streak": int(row[12] or 0),
        }
        self._apply_period_rollover(stats)
        return stats

    async def _save_player_stats(self, guild_id: int, user_id: int, stats: dict[str, Any]):
        await self.db.upsert_emoji_quiz_player_stats(
            int(guild_id),
            int(user_id),
            int(stats["total_points"]),
            int(stats["weekly_points"]),
            str(stats.get("weekly_key") or ""),
            int(stats["monthly_points"]),
            str(stats.get("monthly_key") or ""),
            int(stats["correct"]),
            int(stats["attempts"]),
            int(stats["rounds_started"]),
            int(stats["rounds_closed"]),
            int(stats["current_streak"]),
            int(stats["best_streak"]),
        )

    async def _reset_previous_winner_streak_if_needed(self, guild_id: int, previous_winner_id: int, new_winner_id: int | None):
        if not previous_winner_id:
            return
        if new_winner_id is not None and int(previous_winner_id) == int(new_winner_id):
            return
        stats = await self._get_player_stats(guild_id, previous_winner_id)
        if int(stats["current_streak"]) <= 0:
            return
        stats["current_streak"] = 0
        await self._save_player_stats(guild_id, previous_winner_id, stats)

    async def _resolve_target(self, guild: discord.Guild, channel_id: int, thread_id: int) -> discord.TextChannel | discord.Thread | None:
        if int(thread_id):
            thread = guild.get_thread(int(thread_id))
            if isinstance(thread, discord.Thread):
                return thread
            try:
                fetched = await self.bot.fetch_channel(int(thread_id))
            except Exception:
                fetched = None
            if isinstance(fetched, discord.Thread):
                return fetched
        if int(channel_id):
            channel = guild.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                return channel
            try:
                fetched = await self.bot.fetch_channel(int(channel_id))
            except Exception:
                fetched = None
            if isinstance(fetched, discord.TextChannel):
                return fetched
        return None

    async def _get_review_forum(self, guild: discord.Guild) -> discord.ForumChannel | None:
        channel_id = self._review_forum_channel_id(guild.id)
        if not channel_id:
            return None
        channel = guild.get_channel(int(channel_id))
        if not channel:
            try:
                channel = await guild.fetch_channel(int(channel_id))
            except Exception:
                channel = None
        return channel if isinstance(channel, discord.ForumChannel) else None

    async def _get_thread(self, guild: discord.Guild, thread_id: int) -> discord.Thread | None:
        thread = guild.get_thread(int(thread_id))
        if thread:
            return thread
        try:
            channel = await guild.fetch_channel(int(thread_id))
        except Exception:
            channel = None
        return channel if isinstance(channel, discord.Thread) else None

    async def _ensure_status_tag(self, forum: discord.ForumChannel, status: str) -> discord.ForumTag | None:
        name = self._status_tag_name(status)
        for tag in forum.available_tags:
            if str(tag.name).lower() == name.lower():
                return tag
        try:
            return await forum.create_tag(name=name)
        except Exception:
            return None

    async def _apply_status_tag(self, thread: discord.Thread, status: str):
        parent = getattr(thread, "parent", None)
        if not isinstance(parent, discord.ForumChannel):
            return
        tag = await self._ensure_status_tag(parent, status)
        if not tag:
            return
        keep = [item for item in list(getattr(thread, "applied_tags", []) or []) if str(item.name).lower() not in self._status_tag_names()]
        if all(int(getattr(item, "id", 0)) != int(tag.id) for item in keep):
            keep.append(tag)
        try:
            await thread.edit(applied_tags=keep)
        except Exception:
            pass

    def _target_ids_from_channel(self, target: discord.TextChannel | discord.Thread) -> tuple[int, int]:
        if isinstance(target, discord.Thread):
            return int(target.parent_id or 0), int(target.id)
        return int(target.id), 0

    def _target_label(self, guild: discord.Guild, state: dict[str, Any]) -> str:
        if int(state.get("target_thread_id") or 0):
            thread = guild.get_thread(int(state["target_thread_id"]))
            return thread.mention if thread else f"<#{int(state['target_thread_id'])}>"
        if int(state.get("target_channel_id") or 0):
            channel = guild.get_channel(int(state["target_channel_id"]))
            return channel.mention if isinstance(channel, discord.TextChannel) else f"<#{int(state['target_channel_id'])}>"
        return "Nicht gesetzt"

    async def _dashboard_stats(self, guild: discord.Guild) -> dict[str, Any]:
        state = await self._guild_state(guild.id)
        top = await self.db.list_emoji_quiz_players_top_alltime(guild.id, limit=1)
        champion = "Noch kein Champion"
        if top:
            user_id = int(top[0][0])
            points = int(top[0][1] or 0)
            member = guild.get_member(user_id)
            champion = f"**{member.display_name if member else user_id}** ({points} Punkte)"
        active = self._rounds.get(guild.id)
        active_state = "Keine Runde aktiv"
        if active:
            active_state = f"**#{active.round_number}** • {active.category_label} • endet {discord.utils.format_dt(active.end_at, style='R')}"
        return {
            "target": self._target_label(guild, state),
            "categories": len(state["enabled_categories"]),
            "players": await self.db.count_emoji_quiz_players(guild.id),
            "rounds": int(state["rounds_total"]),
            "champion": champion,
            "active_state": active_state,
        }

    async def is_champion(self, guild_id: int, user_id: int) -> bool:
        top = await self.db.list_emoji_quiz_players_top_alltime(guild_id, limit=1)
        if not top:
            return False
        return int(top[0][0] or 0) == int(user_id) and int(top[0][1] or 0) > 0

    async def can_manage(self, member: discord.Member, action: str) -> bool:
        if self.permission_service.member_has_action_access(member, action):
            missing = self.permission_service.missing_action_permission(member, action)
            if not missing:
                return True
        return await self.is_champion(member.guild.id, member.id)

    async def configure_review_forum(self, guild: discord.Guild, forum_channel: discord.ForumChannel):
        await self.settings.set_guild_override(self.db, guild.id, "emoji_quiz.review_forum_channel_id", int(forum_channel.id))

    async def setup_target(
        self,
        guild: discord.Guild,
        target: discord.TextChannel | discord.Thread,
        timeout_seconds: int | None = None,
        auto_interval_seconds: int | None = None,
        auto_enabled: bool | None = None,
        enabled_categories: list[str] | None = None,
        review_forum: discord.ForumChannel | None = None,
    ):
        state = await self._guild_state(guild.id)
        channel_id, thread_id = self._target_ids_from_channel(target)
        state["target_channel_id"] = channel_id
        state["target_thread_id"] = thread_id
        if timeout_seconds is not None:
            state["round_timeout_seconds"] = max(20, int(timeout_seconds))
        state["auto_enabled"] = False
        if enabled_categories is not None:
            cleaned = await self._clean_category_inputs(guild.id, enabled_categories)
            if cleaned:
                state["enabled_categories"] = cleaned
        await self._save_guild_state(state)
        if review_forum is not None:
            await self.configure_review_forum(guild, review_forum)
        self._next_auto_at.pop(guild.id, None)
        await self.ensure_panel(guild, target)

    async def set_auto(self, guild_id: int, enabled: bool, interval_seconds: int | None = None):
        state = await self._guild_state(guild_id)
        state["auto_enabled"] = bool(enabled)
        if interval_seconds is not None:
            state["auto_interval_seconds"] = max(30, int(interval_seconds))
        await self._save_guild_state(state)
        self._next_auto_at[guild_id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))

    async def set_categories(self, guild_id: int, categories: list[str]):
        state = await self._guild_state(guild_id)
        cleaned = await self._clean_category_inputs(guild_id, categories)
        catalog = await self._base_category_catalog(guild_id)
        state["enabled_categories"] = cleaned or self._ordered_category_keys(catalog)
        await self._save_guild_state(state)

    async def refresh_dashboard(self, guild: discord.Guild):
        if not self._enabled(guild.id):
            return
        state = await self._guild_state(guild.id)
        target = await self._resolve_target(guild, int(state["target_channel_id"]), int(state["target_thread_id"]))
        if target is None:
            return
        await self.ensure_panel(guild, target)

    def _is_dashboard_message(self, message: discord.Message) -> bool:
        try:
            for row in list(message.components or []):
                for item in list(getattr(row, "children", []) or []):
                    custom_id = str(getattr(item, "custom_id", "") or "")
                    if custom_id.startswith("starry:emoji_quiz:"):
                        return True
        except Exception:
            return False
        return False

    async def _find_existing_dashboard_message(self, target: discord.TextChannel | discord.Thread) -> discord.Message | None:
        me = getattr(self.bot, "user", None)
        if not me:
            return None
        try:
            async for message in target.history(limit=40):
                if int(message.author.id) != int(me.id):
                    continue
                if self._is_dashboard_message(message):
                    return message
        except Exception:
            return None
        return None

    async def build_dashboard(self, guild: discord.Guild, stats: dict[str, Any]) -> discord.ui.LayoutView:
        from bot.modules.emoji_quiz.views.emoji_quiz_panel import EmojiQuizButton, EmojiQuizCategorySelect

        options = await self.category_select_options(guild.id)
        return build_dashboard_view(
            self.settings,
            guild,
            stats,
            EmojiQuizCategorySelect(category_options=options, disabled=not options),
            [
                EmojiQuizButton("random"),
                EmojiQuizButton("leaderboard_weekly"),
                EmojiQuizButton("leaderboard_monthly"),
                EmojiQuizButton("streaks"),
                EmojiQuizButton("stats"),
                EmojiQuizButton("submit_question"),
                EmojiQuizButton("submit_user"),
            ],
        )

    async def ensure_panel(self, guild: discord.Guild, target: discord.TextChannel | discord.Thread):
        stats = await self._dashboard_stats(guild)
        view = await self.build_dashboard(guild, stats)
        state = await self._guild_state(guild.id)
        message_id = int(state["panel_message_id"] or 0)
        if message_id:
            try:
                message = await target.fetch_message(message_id)
                await message.edit(view=view)
                return
            except Exception:
                pass
        reuse = await self._find_existing_dashboard_message(target)
        if reuse:
            try:
                await reuse.edit(view=view)
                state["panel_message_id"] = int(reuse.id)
                await self._save_guild_state(state)
                return
            except Exception:
                pass
        message = await target.send(view=view)
        state["panel_message_id"] = int(message.id)
        await self._save_guild_state(state)

    def _remember_recent_answer(self, guild_id: int, answer: str):
        buf = self._recent_answers.get(guild_id, [])
        buf.append(str(answer))
        if len(buf) > 15:
            buf = buf[-15:]
        self._recent_answers[guild_id] = buf

    def _pick_entry(
        self,
        guild_id: int,
        categories: list[str],
        question_pool: dict[str, list[dict[str, Any]]],
        force_category: str | None = None,
    ) -> tuple[str, dict[str, Any]] | tuple[None, None]:
        if force_category:
            keys = [force_category] if force_category in categories else []
        else:
            keys = list(categories)
            random.shuffle(keys)
        if not keys:
            return None, None
        recent = set(self._recent_answers.get(guild_id, []))
        fallback: tuple[str, dict[str, Any]] | None = None
        for key in keys:
            items = list(question_pool.get(key) or [])
            random.shuffle(items)
            for item in items:
                answer = str(item.get("answer") or "")
                if not answer:
                    continue
                if fallback is None:
                    fallback = (key, item)
                if answer not in recent:
                    return key, item
        return fallback or (None, None)

    async def start_round(
        self,
        guild: discord.Guild,
        actor: discord.Member | None = None,
        category_key: str | None = None,
        auto_started: bool = False,
        target_override: discord.TextChannel | discord.Thread | None = None,
    ) -> tuple[bool, str]:
        if not self._enabled(guild.id):
            return False, "Emoji-Quiz ist deaktiviert."
        if guild.id in self._rounds:
            return False, "Es läuft bereits ein Emoji-Rätsel."
        state = await self._guild_state(guild.id)
        target = target_override or await self._resolve_target(guild, int(state["target_channel_id"]), int(state["target_thread_id"]))
        if target is None:
            return False, "Kein Ziel-Channel oder Thread konfiguriert."
        target_channel_id, target_thread_id = self._target_ids_from_channel(target)
        if category_key:
            category_key = await self.resolve_category_key(guild.id, category_key, enabled_only=True)
            if not category_key:
                return False, "Diese Kategorie ist hier nicht aktiviert."
        catalog = await self._base_category_catalog(guild.id)
        question_pool = await self._question_pool_map(guild.id)
        categories = [str(key) for key in state["enabled_categories"] if str(key) in catalog]
        chosen_key, entry = self._pick_entry(guild.id, categories, question_pool, force_category=category_key)
        if not chosen_key or not entry:
            return False, "Keine Emoji-Rätsel verfügbar."
        payload = catalog[chosen_key]
        round_number = int(state["rounds_total"]) + 1
        end_at = datetime.now(timezone.utc) + timedelta(seconds=int(state["round_timeout_seconds"]))
        answer = str(entry["answer"])
        aliases = {self._normalize(answer)}
        for alias in list(entry.get("aliases") or []):
            aliases.add(self._normalize(str(alias)))
        message = await target.send(
            embed=build_round_embed(
                self.settings,
                guild,
                str(payload["label"]),
                str(entry["prompt"]),
                end_at,
                round_number,
                started_by=int(actor.id) if actor else None,
                auto_started=auto_started,
                hints_enabled=self._reveal_hints_enabled(guild.id),
            )
        )
        active = ActiveEmojiRound(
            guild_id=int(guild.id),
            target_channel_id=int(target_channel_id),
            target_thread_id=int(target_thread_id),
            prompt_message_id=int(message.id),
            category_key=str(chosen_key),
            category_label=str(payload["label"]),
            prompt=str(entry["prompt"]),
            answer=answer,
            aliases=aliases,
            round_number=int(round_number),
            started_by=int(actor.id) if actor else None,
            auto_started=bool(auto_started),
            end_at=end_at,
        )
        self._rounds[guild.id] = active
        if actor and not auto_started:
            stats = await self._get_player_stats(guild.id, actor.id)
            stats["rounds_started"] += 1
            await self._save_player_stats(guild.id, actor.id, stats)
        state["rounds_total"] = round_number
        await self._save_guild_state(state)
        self._next_auto_at[guild.id] = end_at + timedelta(seconds=int(state["auto_interval_seconds"]))

        async def _timeout():
            await asyncio.sleep(max(1, int((active.end_at - datetime.now(timezone.utc)).total_seconds())))
            claimed = await self._claim_round(guild.id, active)
            if claimed:
                await self._close_without_winner(guild, active, "Timeout")

        active.timeout_task = asyncio.create_task(_timeout())
        if self._reveal_hints_enabled(guild.id):
            active.hint_task = asyncio.create_task(self._run_hint_sequence(guild, active))
        self._remember_recent_answer(guild.id, answer)
        await self.refresh_dashboard(guild)
        return True, f"Emoji-Rätsel in **{payload['label']}** gestartet."

    async def _claim_round(self, guild_id: int, expected: ActiveEmojiRound) -> bool:
        lock = self._resolve_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._resolve_locks[guild_id] = lock
        async with lock:
            current = self._rounds.get(guild_id)
            if current is None or current is not expected:
                return False
            self._rounds.pop(guild_id, None)
            return True

    async def _delete_prompt(self, target: discord.TextChannel | discord.Thread, message_id: int):
        try:
            await target.get_partial_message(int(message_id)).delete()
        except Exception:
            pass

    async def _send_transient_embed(
        self,
        target: discord.TextChannel | discord.Thread,
        embed: discord.Embed,
        *,
        delete_after: int | None = None,
    ):
        try:
            await target.send(
                embed=embed,
                delete_after=int(delete_after or self.TRANSIENT_MESSAGE_DELETE_AFTER),
            )
        except Exception:
            pass

    async def _close_without_winner(self, guild: discord.Guild, round_: ActiveEmojiRound, reason: str, closed_by: discord.Member | None = None):
        state = await self._guild_state(guild.id)
        await self._reset_previous_winner_streak_if_needed(guild.id, int(state.get("last_winner_id") or 0), None)
        state["last_winner_id"] = 0
        await self._save_guild_state(state)
        target = await self._resolve_target(guild, round_.target_channel_id, round_.target_thread_id)
        if round_.timeout_task:
            round_.timeout_task.cancel()
        if round_.hint_task:
            round_.hint_task.cancel()
        if isinstance(target, (discord.TextChannel, discord.Thread)):
            await self._delete_prompt(target, round_.prompt_message_id)
            await self._send_transient_embed(
                target,
                build_closed_embed(self.settings, guild, round_.answer, round_.category_label, reason),
            )
        if closed_by:
            stats = await self._get_player_stats(guild.id, closed_by.id)
            stats["rounds_closed"] += 1
            await self._save_player_stats(guild.id, closed_by.id, stats)
        self._next_auto_at[guild.id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))
        await self.refresh_dashboard(guild)

    async def stop_round(self, guild: discord.Guild, actor: discord.Member | None = None, reason: str = "Manuell gestoppt") -> tuple[bool, str]:
        round_ = self._rounds.get(guild.id)
        if not round_:
            return False, "Es läuft aktuell kein Emoji-Rätsel."
        claimed = await self._claim_round(guild.id, round_)
        if not claimed:
            return False, "Das Rätsel wurde bereits verarbeitet."
        await self._close_without_winner(guild, round_, reason, closed_by=actor)
        return True, "Emoji-Rätsel geschlossen."

    async def _resolve_winner(self, guild: discord.Guild, round_: ActiveEmojiRound, winner: discord.Member):
        state = await self._guild_state(guild.id)
        previous_winner_id = int(state.get("last_winner_id") or 0)
        await self._reset_previous_winner_streak_if_needed(guild.id, previous_winner_id, winner.id)
        stats = await self._get_player_stats(guild.id, winner.id)
        self._apply_period_rollover(stats)
        gain = self._points_per_win(guild.id)
        stats["total_points"] += gain
        stats["weekly_points"] += gain
        stats["monthly_points"] += gain
        stats["correct"] += 1
        stats["current_streak"] = int(stats["current_streak"]) + 1 if previous_winner_id == int(winner.id) else 1
        stats["best_streak"] = max(int(stats["best_streak"]), int(stats["current_streak"]))
        await self._save_player_stats(guild.id, winner.id, stats)
        state["last_winner_id"] = int(winner.id)
        await self._save_guild_state(state)
        target = await self._resolve_target(guild, round_.target_channel_id, round_.target_thread_id)
        if round_.timeout_task:
            round_.timeout_task.cancel()
        if round_.hint_task:
            round_.hint_task.cancel()
        if isinstance(target, (discord.TextChannel, discord.Thread)):
            await self._delete_prompt(target, round_.prompt_message_id)
            await self._send_transient_embed(
                target,
                build_result_embed(
                    self.settings,
                    guild,
                    winner.id,
                    round_.answer,
                    round_.category_label,
                    gain,
                    int(stats["total_points"]),
                    int(stats["current_streak"]),
                ),
            )
        self._next_auto_at[guild.id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))
        await self.refresh_dashboard(guild)

    async def _cleanup_answer_message(self, message: discord.Message):
        try:
            await asyncio.sleep(self.ANSWER_MESSAGE_DELETE_AFTER)
            await message.delete()
        except Exception:
            pass

    async def handle_message(self, message: discord.Message):
        if not message.guild or not isinstance(message.author, discord.Member) or message.author.bot:
            return
        if not self._enabled(message.guild.id):
            return
        round_ = self._rounds.get(message.guild.id)
        if not round_:
            return
        if round_.target_thread_id:
            if int(message.channel.id) != int(round_.target_thread_id):
                return
        elif int(message.channel.id) != int(round_.target_channel_id):
            return
        content = str(message.content or "").strip()
        if not content or content.startswith("!"):
            return
        stats = await self._get_player_stats(message.guild.id, message.author.id)
        stats["attempts"] += 1
        await self._save_player_stats(message.guild.id, message.author.id, stats)
        round_.attempts += 1
        normalized = self._normalize(content)
        is_correct = normalized in round_.aliases
        try:
            await message.add_reaction("✅" if is_correct else "❌")
        except Exception:
            pass
        asyncio.create_task(self._cleanup_answer_message(message))
        if not is_correct:
            return
        claimed = await self._claim_round(message.guild.id, round_)
        if claimed:
            await self._resolve_winner(message.guild, round_, message.author)

    async def stats_for(self, guild_id: int, user_id: int) -> dict[str, Any]:
        return await self._get_player_stats(guild_id, user_id)

    async def stats_summary_embed(self, guild_id: int, user_id: int, guild: discord.Guild | None = None) -> discord.Embed:
        stats = await self._get_player_stats(guild_id, user_id)
        member = guild.get_member(user_id) if guild else None
        name = member.display_name if member else str(user_id)
        return build_stats_embed(
            self.settings,
            guild,
            int(user_id),
            name,
            stats,
        )

    async def panel_start_category(self, interaction: discord.Interaction, category_key: str) -> tuple[bool, str]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "Nur im Server nutzbar."
        if not await self.can_manage(interaction.user, "emoji_quiz_start"):
            return False, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt."
        target = interaction.channel if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)) else None
        return await self.start_round(interaction.guild, actor=interaction.user, category_key=str(category_key), target_override=target)

    async def panel_start_random(self, interaction: discord.Interaction) -> tuple[bool, str]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "Nur im Server nutzbar."
        if not await self.can_manage(interaction.user, "emoji_quiz_start"):
            return False, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt."
        target = interaction.channel if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)) else None
        return await self.start_round(interaction.guild, actor=interaction.user, target_override=target)

    async def open_question_submit_modal(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        await interaction.response.send_modal(EmojiQuestionSubmitModal(self))

    async def open_category_submit_modal(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        await interaction.response.send_modal(EmojiCategorySubmitModal(self))

    async def open_user_submit_modal(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        await interaction.response.send_modal(EmojiUserSubmitModal(self))

    def _submission_dict_from_row(self, row) -> dict[str, Any] | None:
        if not row:
            return None
        try:
            aliases = json.loads(str(row[11] or "[]")) if row[11] else []
        except Exception:
            aliases = []
        return {
            "submission_id": int(row[0]),
            "guild_id": int(row[1]),
            "user_id": int(row[2]),
            "thread_id": int(row[3]),
            "message_id": int(row[4]),
            "submission_type": str(row[5] or "question"),
            "status": str(row[6] or "pending"),
            "category_key": self._canonical_category_key(str(row[7] or "")),
            "category_label": str(row[8] or self._canonical_category_key(str(row[7] or "")) or ""),
            "prompt": str(row[9] or ""),
            "answer": str(row[10] or ""),
            "aliases": list(aliases or []),
            "subject_user_id": int(row[12]) if row[12] else None,
            "created_at": str(row[13] or ""),
            "decided_by": int(row[14]) if row[14] else None,
            "decided_at": str(row[15]) if row[15] else None,
        }

    async def _create_submission(
        self,
        interaction: discord.Interaction,
        submission_type: str,
        *,
        category_key: str,
        category_label: str,
        prompt: str,
        answer: str,
        aliases: list[str],
        subject_user_id: int | None = None,
    ):
        if not interaction.guild or not interaction.user:
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        forum = await self._get_review_forum(interaction.guild)
        if not forum:
            return await _ephemeral(interaction, "Review-Forum ist nicht konfiguriert. Nutze `/emojiquiz setup` mit Forum-Channel.")
        pending_tag = await self._ensure_status_tag(forum, "pending")
        view = build_submission_view(
            self.settings,
            interaction.guild,
            {
                "user_id": int(interaction.user.id),
                "submission_type": submission_type,
                "status": "pending",
                "category_key": category_key,
                "category_label": category_label,
                "prompt": prompt,
                "answer": answer,
                "aliases": aliases,
                "subject_user_id": subject_user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        kwargs: dict[str, Any] = {"name": self._submission_thread_name(interaction.user, submission_type), "view": view}
        if pending_tag:
            kwargs["applied_tags"] = [pending_tag]
        try:
            created = await forum.create_thread(**kwargs)
        except Exception:
            return await _ephemeral(interaction, "Konnte die Einreichung im Review-Forum nicht erstellen.")
        submission_id = await self.db.create_emoji_quiz_submission(
            guild_id=int(interaction.guild.id),
            user_id=int(interaction.user.id),
            thread_id=int(created.thread.id),
            message_id=int(created.message.id),
            submission_type=submission_type,
            category_key=category_key,
            category_label=category_label,
            prompt=prompt,
            answer=answer,
            aliases_json=json.dumps(aliases, ensure_ascii=False),
            subject_user_id=subject_user_id,
        )
        try:
            await created.thread.edit(name=self._submission_thread_name(interaction.user, submission_type, submission_id))
        except Exception:
            pass
        await _ephemeral(interaction, f"Einreichung erstellt: {created.thread.mention}")

    async def submit_question(self, interaction: discord.Interaction, *, category_raw: str, prompt: str, answer: str, aliases_raw: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        clean_prompt = self._clean_text(prompt)
        clean_answer = self._clean_text(answer)
        if len(clean_prompt) < 2:
            return await _ephemeral(interaction, "Die Emoji-Frage ist zu kurz.")
        if len(clean_answer) < 2:
            return await _ephemeral(interaction, "Die Antwort ist zu kurz.")
        catalog = await self._base_category_catalog(interaction.guild.id)
        category_key = self._match_category_key(catalog, category_raw)
        if not category_key:
            return await _ephemeral(interaction, "Kategorie nicht gefunden. Reiche erst eine neue Kategorie ein oder nutze eine bestehende.")
        if category_key == "user":
            return await _ephemeral(interaction, "Für persönliche Emoji-Rätsel nutze bitte den `User`-Button.")
        await self._create_submission(
            interaction,
            "question",
            category_key=category_key,
            category_label=str(catalog[category_key]["label"]),
            prompt=clean_prompt,
            answer=clean_answer,
            aliases=self._dedupe_aliases([clean_answer, *self._parse_aliases(aliases_raw)]),
        )

    async def submit_category(self, interaction: discord.Interaction, *, label: str, description: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        clean_label = self._clean_text(label)
        clean_description = self._clean_text(description)
        if len(clean_label) < 3:
            return await _ephemeral(interaction, "Der Kategoriename ist zu kurz.")
        if len(clean_description) < 10:
            return await _ephemeral(interaction, "Bitte beschreibe die Kategorie etwas genauer.")
        catalog = await self._base_category_catalog(interaction.guild.id)
        category_key = self._slugify_category_key(clean_label)
        if category_key in catalog or any(self._normalize(str(payload["label"])) == self._normalize(clean_label) for payload in catalog.values()):
            return await _ephemeral(interaction, "Diese Kategorie gibt es bereits.")
        await self._create_submission(
            interaction,
            "category",
            category_key=category_key,
            category_label=clean_label,
            prompt=clean_label,
            answer=clean_description,
            aliases=[],
        )

    async def submit_user_question(self, interaction: discord.Interaction, *, prompt: str, aliases_raw: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        clean_prompt = self._clean_text(prompt)
        if len(clean_prompt) < 2:
            return await _ephemeral(interaction, "Die Emoji-Beschreibung ist zu kurz.")
        catalog = await self._base_category_catalog(interaction.guild.id)
        await self._create_submission(
            interaction,
            "user_question",
            category_key="user",
            category_label=str(catalog.get("user", {}).get("label") or "User"),
            prompt=clean_prompt,
            answer=self._clean_text(interaction.user.display_name or interaction.user.name),
            aliases=self._dedupe_aliases(
                [
                    str(interaction.user.display_name or interaction.user.name),
                    str(interaction.user.name or ""),
                    str(getattr(interaction.user, "global_name", None) or ""),
                    *self._parse_aliases(aliases_raw),
                ]
            ),
            subject_user_id=int(interaction.user.id),
        )

    async def _refresh_submission_message(self, guild: discord.Guild, submission_id: int):
        data = self._submission_dict_from_row(await self.db.get_emoji_quiz_submission(int(submission_id)))
        if not data:
            return
        thread = await self._get_thread(guild, int(data["thread_id"]))
        if not thread:
            return
        try:
            message = await thread.fetch_message(int(data["message_id"]))
        except Exception:
            return
        try:
            await message.edit(view=build_submission_view(self.settings, guild, data))
        except Exception:
            pass
        await self._apply_status_tag(thread, str(data["status"]))

    async def _accept_submission(self, guild: discord.Guild, data: dict[str, Any]) -> tuple[bool, str]:
        submission_type = str(data["submission_type"])
        category_key = str(data.get("category_key") or "").strip()
        category_label = str(data.get("category_label") or category_key or "Kategorie").strip()
        if submission_type == "category":
            if not category_key:
                return False, "Der Kategorie-Key fehlt."
            if category_key in EMOJI_QUIZ_BANK:
                return False, "Diese Kategorie existiert bereits als feste Kategorie."
            await self.db.create_emoji_quiz_custom_category(
                guild_id=guild.id,
                category_key=category_key,
                label=category_label,
                description=str(data.get("answer") or "").strip() or None,
                created_by=int(data["user_id"]),
                source_submission_id=int(data["submission_id"]),
            )
            await self._ensure_category_enabled(guild.id, category_key)
            return True, f"Kategorie **{category_label}** angenommen."
        if submission_type == "user_question":
            category_key = "user"
            await self._ensure_category_enabled(guild.id, "user")
        catalog = await self._base_category_catalog(guild.id)
        if category_key not in catalog:
            return False, "Die Ziel-Kategorie existiert nicht."
        await self.db.create_emoji_quiz_custom_question(
            guild_id=guild.id,
            category_key=category_key,
            prompt=str(data.get("prompt") or ""),
            answer=str(data.get("answer") or ""),
            aliases_json=json.dumps(self._dedupe_aliases([str(data.get("answer") or ""), *list(data.get("aliases") or [])]), ensure_ascii=False),
            submitted_by=int(data["user_id"]),
            source_submission_id=int(data["submission_id"]),
            subject_user_id=int(data["subject_user_id"]) if data.get("subject_user_id") else None,
        )
        return True, f"{self._submission_type_label(submission_type)} angenommen."

    async def set_submission_status(self, interaction: discord.Interaction, status: str):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await _ephemeral(interaction, "Nur im Server nutzbar.")
        if not isinstance(interaction.channel, discord.Thread):
            return await _ephemeral(interaction, "Nur im Einreichungs-Thread nutzbar.")
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in {"accepted", "rejected"}:
            return await _ephemeral(interaction, "Ungültiger Status.")
        err = self.permission_service.action_error(interaction.user, "emoji_quiz_accept" if normalized_status == "accepted" else "emoji_quiz_reject")
        if err:
            return await _ephemeral(interaction, err)
        data = self._submission_dict_from_row(await self.db.get_emoji_quiz_submission_by_thread(interaction.guild.id, interaction.channel.id))
        if not data:
            return await _ephemeral(interaction, "Einreichung nicht gefunden.")
        if str(data["status"]) != "pending":
            return await _ephemeral(interaction, "Diese Einreichung wurde bereits geprüft.")
        message = f"{self._submission_type_label(str(data['submission_type']))} abgelehnt."
        if normalized_status == "accepted":
            ok, message = await self._accept_submission(interaction.guild, data)
            if not ok:
                return await _ephemeral(interaction, message)
        await self.db.set_emoji_quiz_submission_status(int(data["submission_id"]), normalized_status, interaction.user.id)
        await self._refresh_submission_message(interaction.guild, int(data["submission_id"]))
        await self.refresh_dashboard(interaction.guild)
        await _ephemeral(interaction, message)

    async def categories_text(self, guild_id: int) -> str:
        lines = [f"{payload['emoji']} **{payload['label']}** ({int(payload['question_count'])} Rätsel)" for payload in await self.category_catalog(guild_id, enabled_only=True)]
        return "\n".join(lines) if lines else "Keine Kategorien aktiv."

    async def tick(self):
        return
