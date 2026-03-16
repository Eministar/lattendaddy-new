from __future__ import annotations

import asyncio
import time
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import discord

from bot.modules.guess_the_number.formatting.guess_number_embeds import (
    build_closed_embed,
    build_dashboard_view,
    build_result_embed,
    build_round_embed,
)
from bot.modules.moderation.services.permission_service import PermissionService


@dataclass
class ActiveGuessRound:
    guild_id: int
    target_channel_id: int
    target_thread_id: int
    prompt_message_id: int
    answer_number: int
    min_number: int
    max_number: int
    round_number: int
    started_by: int | None
    auto_started: bool
    end_at: datetime
    timeout_task: asyncio.Task | None = None
    total_guesses: int = 0


class GuessNumberService:
    _INT_RE = re.compile(r"^-?\d+$")

    def __init__(self, bot: discord.Client, settings, db, logger):
        self.bot = bot
        self.settings = settings
        self.db = db
        self.logger = logger
        self.permission_service = PermissionService(settings, db)
        self._rounds: dict[int, ActiveGuessRound] = {}
        self._resolve_locks: dict[int, asyncio.Lock] = {}
        self._guess_cooldowns: dict[tuple[int, int], float] = {}
        self._next_auto_at: dict[int, datetime] = {}

    def _enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "guess_number.enabled", True))

    def _default_min(self, guild_id: int) -> int:
        return int(self.settings.get_guild_int(guild_id, "guess_number.default_min", 1) or 1)

    def _default_max(self, guild_id: int) -> int:
        return int(self.settings.get_guild_int(guild_id, "guess_number.default_max", 100) or 100)

    def _default_timeout_seconds(self, guild_id: int) -> int:
        return max(20, int(self.settings.get_guild_int(guild_id, "guess_number.round_timeout_seconds", 180) or 180))

    def _default_auto_interval_seconds(self, guild_id: int) -> int:
        return max(30, int(self.settings.get_guild_int(guild_id, "guess_number.auto_interval_seconds", 180) or 180))

    def _hint_messages_enabled(self, guild_id: int) -> bool:
        return bool(self.settings.get_guild_bool(guild_id, "guess_number.hint_messages", True))

    def _guess_cooldown_seconds(self, guild_id: int) -> int:
        return max(0, int(self.settings.get_guild_int(guild_id, "guess_number.guess_cooldown_seconds", 0) or 0))

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
            stats["weekly_wins"] = 0
        if str(stats.get("monthly_key") or "") != month_key:
            stats["monthly_key"] = month_key
            stats["monthly_wins"] = 0

    async def _guild_state(self, guild_id: int) -> dict[str, Any]:
        row = await self.db.get_guess_number_guild(int(guild_id))
        defaults = {
            "guild_id": int(guild_id),
            "target_channel_id": 0,
            "target_thread_id": 0,
            "panel_message_id": 0,
            "default_min": self._default_min(guild_id),
            "default_max": self._default_max(guild_id),
            "round_timeout_seconds": self._default_timeout_seconds(guild_id),
            "auto_enabled": False,
            "auto_interval_seconds": self._default_auto_interval_seconds(guild_id),
            "rounds_total": 0,
            "last_winner_id": 0,
        }
        if not row:
            return defaults
        return {
            "guild_id": int(row[0]),
            "target_channel_id": int(row[1] or 0),
            "target_thread_id": int(row[2] or 0),
            "panel_message_id": int(row[3] or 0),
            "default_min": int(row[4] or defaults["default_min"]),
            "default_max": int(row[5] or defaults["default_max"]),
            "round_timeout_seconds": int(row[6] or defaults["round_timeout_seconds"]),
            "auto_enabled": bool(int(row[7] or 0)),
            "auto_interval_seconds": int(row[8] or defaults["auto_interval_seconds"]),
            "rounds_total": int(row[9] or 0),
            "last_winner_id": int(row[10] or 0),
        }

    async def _save_guild_state(self, state: dict[str, Any]):
        await self.db.upsert_guess_number_guild(
            int(state["guild_id"]),
            int(state.get("target_channel_id") or 0) or None,
            int(state.get("target_thread_id") or 0) or None,
            int(state.get("panel_message_id") or 0) or None,
            int(state.get("default_min") or 1),
            int(state.get("default_max") or 100),
            int(state.get("round_timeout_seconds") or 180),
            bool(state.get("auto_enabled")),
            int(state.get("auto_interval_seconds") or 180),
            int(state.get("rounds_total") or 0),
            int(state.get("last_winner_id") or 0) or None,
        )

    async def _get_player_stats(self, guild_id: int, user_id: int) -> dict[str, Any]:
        row = await self.db.get_guess_number_player_stats(int(guild_id), int(user_id))
        week_key, month_key = self._period_keys()
        if not row:
            return {
                "total_wins": 0,
                "weekly_wins": 0,
                "weekly_key": week_key,
                "monthly_wins": 0,
                "monthly_key": month_key,
                "total_guesses": 0,
                "rounds_started": 0,
                "rounds_closed": 0,
                "current_streak": 0,
                "best_streak": 0,
            }
        stats = {
            "total_wins": int(row[2] or 0),
            "weekly_wins": int(row[3] or 0),
            "weekly_key": str(row[4] or ""),
            "monthly_wins": int(row[5] or 0),
            "monthly_key": str(row[6] or ""),
            "total_guesses": int(row[7] or 0),
            "rounds_started": int(row[8] or 0),
            "rounds_closed": int(row[9] or 0),
            "current_streak": int(row[10] or 0),
            "best_streak": int(row[11] or 0),
        }
        self._apply_period_rollover(stats)
        return stats

    async def _save_player_stats(self, guild_id: int, user_id: int, stats: dict[str, Any]):
        await self.db.upsert_guess_number_player_stats(
            int(guild_id),
            int(user_id),
            int(stats["total_wins"]),
            int(stats["weekly_wins"]),
            str(stats.get("weekly_key") or ""),
            int(stats["monthly_wins"]),
            str(stats.get("monthly_key") or ""),
            int(stats["total_guesses"]),
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

    def _target_ids_from_channel(self, target: discord.TextChannel | discord.Thread) -> tuple[int, int]:
        if isinstance(target, discord.Thread):
            return int(target.parent_id or 0), int(target.id)
        return int(target.id), 0

    def _target_label(self, guild: discord.Guild, state: dict[str, Any]) -> str:
        thread_id = int(state.get("target_thread_id") or 0)
        channel_id = int(state.get("target_channel_id") or 0)
        if thread_id:
            thread = guild.get_thread(thread_id)
            return thread.mention if thread else f"<#{thread_id}>"
        if channel_id:
            channel = guild.get_channel(channel_id)
            return channel.mention if isinstance(channel, discord.TextChannel) else f"<#{channel_id}>"
        return "Nicht gesetzt"

    async def _dashboard_stats(self, guild: discord.Guild) -> dict[str, Any]:
        state = await self._guild_state(guild.id)
        top = await self.db.list_guess_number_players_top_alltime(guild.id, limit=1)
        champion = "Noch kein Champion"
        if top:
            user_id = int(top[0][0])
            wins = int(top[0][1] or 0)
            member = guild.get_member(user_id)
            champion = f"**{member.display_name if member else user_id}** ({wins} Siege)"
        active = self._rounds.get(guild.id)
        active_state = "Keine Runde aktiv"
        if active:
            active_state = f"**#{active.round_number}** • {active.min_number}-{active.max_number} • endet {discord.utils.format_dt(active.end_at, style='R')}"
        return {
            "target": self._target_label(guild, state),
            "default_min": int(state["default_min"]),
            "default_max": int(state["default_max"]),
            "players": await self.db.count_guess_number_players(guild.id),
            "rounds": int(state["rounds_total"]),
            "champion": champion,
            "auto_status": f"{'An' if state['auto_enabled'] else 'Aus'} ({int(state['auto_interval_seconds'])}s)",
            "active_state": active_state,
        }

    async def is_champion(self, guild_id: int, user_id: int) -> bool:
        top = await self.db.list_guess_number_players_top_alltime(guild_id, limit=1)
        if not top:
            return False
        return int(top[0][0] or 0) == int(user_id) and int(top[0][1] or 0) > 0

    async def can_manage(self, member: discord.Member, action: str) -> bool:
        if self.permission_service.member_has_action_access(member, action):
            missing = self.permission_service.missing_action_permission(member, action)
            if not missing:
                return True
        return await self.is_champion(member.guild.id, member.id)

    async def setup_target(
        self,
        guild: discord.Guild,
        target: discord.TextChannel | discord.Thread,
        default_min: int | None = None,
        default_max: int | None = None,
        timeout_seconds: int | None = None,
        auto_interval_seconds: int | None = None,
        auto_enabled: bool | None = None,
    ):
        state = await self._guild_state(guild.id)
        channel_id, thread_id = self._target_ids_from_channel(target)
        state["target_channel_id"] = channel_id
        state["target_thread_id"] = thread_id
        if default_min is not None:
            state["default_min"] = int(default_min)
        if default_max is not None:
            state["default_max"] = int(default_max)
        if timeout_seconds is not None:
            state["round_timeout_seconds"] = max(20, int(timeout_seconds))
        if auto_interval_seconds is not None:
            state["auto_interval_seconds"] = max(30, int(auto_interval_seconds))
        if auto_enabled is not None:
            state["auto_enabled"] = bool(auto_enabled)
        await self._save_guild_state(state)
        if state["auto_enabled"]:
            self._next_auto_at[guild.id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))
        await self.ensure_panel(guild, target)

    async def set_default_range(self, guild_id: int, min_number: int, max_number: int):
        state = await self._guild_state(guild_id)
        state["default_min"] = int(min_number)
        state["default_max"] = int(max_number)
        await self._save_guild_state(state)

    async def set_auto(self, guild_id: int, enabled: bool, interval_seconds: int | None = None):
        state = await self._guild_state(guild_id)
        state["auto_enabled"] = bool(enabled)
        if interval_seconds is not None:
            state["auto_interval_seconds"] = max(30, int(interval_seconds))
        await self._save_guild_state(state)
        self._next_auto_at[guild_id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))

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
                    if custom_id.startswith("starry:guess_dash:"):
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

    def build_dashboard(self, guild: discord.Guild, stats: dict[str, Any]) -> discord.ui.LayoutView:
        from bot.modules.guess_the_number.views.guess_number_panel import GuessDashboardButton
        buttons = [
            GuessDashboardButton("start"),
            GuessDashboardButton("stop"),
            GuessDashboardButton("leaderboard_weekly"),
            GuessDashboardButton("leaderboard_monthly"),
            GuessDashboardButton("streaks"),
            GuessDashboardButton("stats"),
            GuessDashboardButton("auto"),
        ]
        return build_dashboard_view(self.settings, guild, stats, buttons)

    async def ensure_panel(self, guild: discord.Guild, target: discord.TextChannel | discord.Thread):
        stats = await self._dashboard_stats(guild)
        view = self.build_dashboard(guild, stats)
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

    async def start_round(
        self,
        guild: discord.Guild,
        actor: discord.Member | None = None,
        min_number: int | None = None,
        max_number: int | None = None,
        auto_started: bool = False,
        target_override: discord.TextChannel | discord.Thread | None = None,
    ) -> tuple[bool, str]:
        if not self._enabled(guild.id):
            return False, "Guess-The-Number ist deaktiviert."
        if guild.id in self._rounds:
            return False, "Es läuft bereits eine Runde."
        state = await self._guild_state(guild.id)
        target = target_override or await self._resolve_target(guild, int(state["target_channel_id"]), int(state["target_thread_id"]))
        if target is None:
            return False, "Kein Ziel-Channel oder Thread konfiguriert."
        target_channel_id, target_thread_id = self._target_ids_from_channel(target)
        lo = int(min_number if min_number is not None else state["default_min"])
        hi = int(max_number if max_number is not None else state["default_max"])
        if lo == hi:
            return False, "Die Range braucht mindestens zwei unterschiedliche Zahlen."
        if lo > hi:
            lo, hi = hi, lo
        timeout_seconds = max(20, int(state["round_timeout_seconds"]))
        round_number = int(state["rounds_total"]) + 1
        answer = random.randint(lo, hi)
        end_at = datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
        embed = build_round_embed(
            self.settings,
            guild,
            int(actor.id) if actor else None,
            lo,
            hi,
            end_at,
            round_number,
            auto_started=auto_started,
        )
        message = await target.send(embed=embed)
        active = ActiveGuessRound(
            guild_id=int(guild.id),
            target_channel_id=int(target_channel_id),
            target_thread_id=int(target_thread_id),
            prompt_message_id=int(message.id),
            answer_number=int(answer),
            min_number=int(lo),
            max_number=int(hi),
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
            await asyncio.sleep(timeout_seconds)
            claimed = await self._claim_round(guild.id, active)
            if not claimed:
                return
            await self._close_without_winner(guild, active, "Timeout")

        active.timeout_task = asyncio.create_task(_timeout())
        await self.refresh_dashboard(guild)
        return True, "Runde gestartet."

    async def _claim_round(self, guild_id: int, expected: ActiveGuessRound) -> bool:
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

    async def _close_without_winner(self, guild: discord.Guild, round_: ActiveGuessRound, reason: str, closed_by: discord.Member | None = None):
        state = await self._guild_state(guild.id)
        await self._reset_previous_winner_streak_if_needed(guild.id, int(state.get("last_winner_id") or 0), None)
        state["last_winner_id"] = 0
        await self._save_guild_state(state)
        target = await self._resolve_target(guild, round_.target_channel_id, round_.target_thread_id)
        if round_.timeout_task:
            round_.timeout_task.cancel()
        if isinstance(target, (discord.TextChannel, discord.Thread)):
            await self._delete_prompt(target, round_.prompt_message_id)
            await target.send(
                embed=build_closed_embed(
                    self.settings,
                    guild,
                    round_.answer_number,
                    round_.total_guesses,
                    reason,
                )
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
            return False, "Es läuft aktuell keine Runde."
        claimed = await self._claim_round(guild.id, round_)
        if not claimed:
            return False, "Die Runde wurde bereits verarbeitet."
        await self._close_without_winner(guild, round_, reason, closed_by=actor)
        return True, "Runde geschlossen."

    async def _resolve_winner(self, guild: discord.Guild, round_: ActiveGuessRound, winner: discord.Member):
        state = await self._guild_state(guild.id)
        previous_winner_id = int(state.get("last_winner_id") or 0)
        await self._reset_previous_winner_streak_if_needed(guild.id, previous_winner_id, winner.id)
        stats = await self._get_player_stats(guild.id, winner.id)
        self._apply_period_rollover(stats)
        stats["total_wins"] += 1
        stats["weekly_wins"] += 1
        stats["monthly_wins"] += 1
        stats["current_streak"] = int(stats["current_streak"]) + 1 if previous_winner_id == int(winner.id) else 1
        stats["best_streak"] = max(int(stats["best_streak"]), int(stats["current_streak"]))
        await self._save_player_stats(guild.id, winner.id, stats)
        state["last_winner_id"] = int(winner.id)
        await self._save_guild_state(state)
        target = await self._resolve_target(guild, round_.target_channel_id, round_.target_thread_id)
        if round_.timeout_task:
            round_.timeout_task.cancel()
        if isinstance(target, (discord.TextChannel, discord.Thread)):
            await self._delete_prompt(target, round_.prompt_message_id)
            await target.send(
                embed=build_result_embed(
                    self.settings,
                    guild,
                    winner.id,
                    round_.answer_number,
                    round_.total_guesses,
                    int(stats["total_wins"]),
                    int(stats["current_streak"]),
                )
            )
        self._next_auto_at[guild.id] = datetime.now(timezone.utc) + timedelta(seconds=int(state["auto_interval_seconds"]))
        await self.refresh_dashboard(guild)

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
        if not self._INT_RE.fullmatch(content):
            return
        cooldown_seconds = self._guess_cooldown_seconds(message.guild.id)
        if cooldown_seconds > 0:
            key = (int(message.guild.id), int(message.author.id))
            now_monotonic = time.monotonic()
            last = float(self._guess_cooldowns.get(key, 0.0) or 0.0)
            if now_monotonic - last < cooldown_seconds:
                return
            self._guess_cooldowns[key] = now_monotonic
        guess = int(content)
        if guess < int(round_.min_number) or guess > int(round_.max_number):
            return
        stats = await self._get_player_stats(message.guild.id, message.author.id)
        stats["total_guesses"] += 1
        await self._save_player_stats(message.guild.id, message.author.id, stats)
        round_.total_guesses += 1
        if guess == int(round_.answer_number):
            claimed = await self._claim_round(message.guild.id, round_)
            if not claimed:
                return
            await self._resolve_winner(message.guild, round_, message.author)
            return
        if self._hint_messages_enabled(message.guild.id):
            hint = "🔼 Zu niedrig." if guess < int(round_.answer_number) else "🔽 Zu hoch."
            try:
                await message.channel.send(f"<@{int(message.author.id)}> {hint}", delete_after=6)
            except Exception:
                pass

    async def stats_for(self, guild_id: int, user_id: int) -> dict[str, Any]:
        return await self._get_player_stats(guild_id, user_id)

    async def stats_summary_text(self, guild_id: int, user_id: int, guild: discord.Guild | None = None) -> str:
        stats = await self._get_player_stats(guild_id, user_id)
        member = guild.get_member(user_id) if guild else None
        name = member.display_name if member else str(user_id)
        return (
            f"**Stats von {name}**\n"
            f"Siege: **{int(stats['total_wins'])}**\n"
            f"Woche: **{int(stats['weekly_wins'])}** • Monat: **{int(stats['monthly_wins'])}**\n"
            f"Tipps: **{int(stats['total_guesses'])}**\n"
            f"Gestartet: **{int(stats['rounds_started'])}** • Geschlossen: **{int(stats['rounds_closed'])}**\n"
            f"Streak: **{int(stats['current_streak'])}** (Best: {int(stats['best_streak'])})"
        )

    async def panel_start(self, interaction: discord.Interaction) -> tuple[bool, str]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "Nur im Server nutzbar."
        if not await self.can_manage(interaction.user, "guess_start"):
            return False, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt."
        target = interaction.channel if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)) else None
        return await self.start_round(interaction.guild, actor=interaction.user, target_override=target)

    async def panel_stop(self, interaction: discord.Interaction) -> tuple[bool, str]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "Nur im Server nutzbar."
        if not await self.can_manage(interaction.user, "guess_stop"):
            return False, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt."
        return await self.stop_round(interaction.guild, actor=interaction.user)

    async def panel_toggle_auto(self, interaction: discord.Interaction) -> tuple[bool, str]:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return False, "Nur im Server nutzbar."
        if not await self.can_manage(interaction.user, "guess_auto"):
            return False, "Keine Rechte. Champion oder freigegebene Staff-Rolle benötigt."
        state = await self._guild_state(interaction.guild.id)
        enabled = not bool(state["auto_enabled"])
        await self.set_auto(interaction.guild.id, enabled)
        await self.refresh_dashboard(interaction.guild)
        return True, f"Auto-Event ist jetzt **{'an' if enabled else 'aus'}**."

    async def tick(self):
        now = datetime.now(timezone.utc)
        for guild in list(self.bot.guilds):
            if not self._enabled(guild.id):
                continue
            if guild.id in self._rounds:
                continue
            state = await self._guild_state(guild.id)
            if not bool(state["auto_enabled"]):
                continue
            if not int(state["target_channel_id"] or 0):
                continue
            due = self._next_auto_at.get(guild.id)
            if due is None:
                self._next_auto_at[guild.id] = now + timedelta(seconds=int(state["auto_interval_seconds"]))
                continue
            if due > now:
                continue
            await self.start_round(guild, actor=None, auto_started=True)
