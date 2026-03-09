from __future__ import annotations

from dataclasses import dataclass
import re

import discord

from bot.core.perms import is_staff


PERSONAL_PERMISSION_ROLE_PREFIX = "perm.user."


def _keyify(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


@dataclass(frozen=True, slots=True)
class ModerationActionSpec:
    key: str
    label: str
    description: str
    discord_permission: str | None = None


MODERATION_ACTIONS: tuple[ModerationActionSpec, ...] = (
    ModerationActionSpec("timeout", "Timeout", "Timeout setzen", "moderate_members"),
    ModerationActionSpec("untimeout", "Untimeout", "Timeout entfernen", "moderate_members"),
    ModerationActionSpec("mute", "Mute", "Mute per Timeout setzen", "moderate_members"),
    ModerationActionSpec("warn", "Warn", "Warnung vergeben", "moderate_members"),
    ModerationActionSpec("kick", "Kick", "User kicken", "kick_members"),
    ModerationActionSpec("ban", "Ban", "User bannen", "ban_members"),
    ModerationActionSpec("unban", "Unban", "User entbannen", "ban_members"),
    ModerationActionSpec("softban", "Softban", "Softban ausfuehren", "ban_members"),
    ModerationActionSpec("purge", "Purge", "Nachrichten loeschen", "manage_messages"),
    ModerationActionSpec("slowmode", "Slowmode", "Slowmode setzen", "manage_channels"),
    ModerationActionSpec("lock", "Lock", "Channel sperren", "manage_channels"),
    ModerationActionSpec("unlock", "Unlock", "Channel entsperren", "manage_channels"),
    ModerationActionSpec("nick", "Nick", "Nickname setzen", "manage_nicknames"),
    ModerationActionSpec("role_add", "Role Add", "Rolle hinzufuegen", "manage_roles"),
    ModerationActionSpec("role_remove", "Role Remove", "Rolle entfernen", "manage_roles"),
    ModerationActionSpec("mass_timeout", "Mass Timeout", "Timeout fuer ganze Rolle", "moderate_members"),
    ModerationActionSpec("warns", "Warns", "Warn-History lesen"),
    ModerationActionSpec("case", "Case", "Case anzeigen"),
    ModerationActionSpec("note", "Note", "Mod-Notiz anlegen"),
    ModerationActionSpec("notes", "Notes", "Mod-Notizen lesen"),
    ModerationActionSpec("unwarn", "Unwarn", "Warns/Timeouts entfernen"),
    ModerationActionSpec("case_reason", "Case Reason", "Case-Grund aendern"),
    ModerationActionSpec("clear_notes", "Clear Notes", "Mod-Notizen loeschen"),
    ModerationActionSpec("say", "Say", "Nachricht als Bot senden", "manage_messages"),
    ModerationActionSpec("backup_save", "Backup Save", "Backup speichern", "manage_guild"),
    ModerationActionSpec("backup_load", "Backup Load", "Backup laden", "manage_guild"),
    ModerationActionSpec("backup_list", "Backup List", "Backups anzeigen", "manage_guild"),
    ModerationActionSpec("backup_diff", "Backup Diff", "Backup-Unterschiede anzeigen", "manage_guild"),
    ModerationActionSpec("backup_autosave", "Backup Autosave", "Auto-Backup umstellen", "manage_guild"),
    ModerationActionSpec("ai_reset_limit", "AI Reset Limit", "AI-Tageslimit resetten", "manage_guild"),
    ModerationActionSpec("application_ask", "Application Ask", "Rueckfrage zur Bewerbung senden", "manage_guild"),
    ModerationActionSpec("application_decide", "Application Decide", "Bewerbungen annehmen oder ablehnen"),
    ModerationActionSpec("application_panel_send", "Application Panel Send", "Bewerbungs-Panel senden", "manage_guild"),
    ModerationActionSpec("beichte_setup", "Beichte Setup", "Beichte konfigurieren", "manage_guild"),
    ModerationActionSpec("beichte_panel", "Beichte Panel", "Beichte-Panel senden", "manage_guild"),
    ModerationActionSpec("beichte_close", "Beichte Close", "Beichte-Thread schliessen", "manage_threads"),
    ModerationActionSpec("beichte_open", "Beichte Open", "Beichte-Thread oeffnen", "manage_threads"),
    ModerationActionSpec("beichte_delete", "Beichte Delete", "Beichte-Thread loeschen", "manage_threads"),
    ModerationActionSpec("beichte_who", "Beichte Who", "Beichte-Ersteller anzeigen", "manage_threads"),
    ModerationActionSpec("suggestion_panel_send", "Suggestion Panel Send", "Vorschlags-Panel senden"),
    ModerationActionSpec("suggestion_status", "Suggestion Status", "Vorschlags-Status aendern"),
    ModerationActionSpec("suggestion_response", "Suggestion Response", "Vorschlags-Antwort setzen"),
    ModerationActionSpec("ticket_claim", "Ticket Claim", "Tickets claimen oder freigeben"),
    ModerationActionSpec("ticket_note", "Ticket Note", "Interne Ticket-Notizen setzen"),
    ModerationActionSpec("ticket_close", "Ticket Close", "Tickets schliessen"),
    ModerationActionSpec("ticket_add", "Ticket Add", "User zu Tickets hinzufuegen"),
    ModerationActionSpec("ticket_reopen", "Ticket Reopen", "Tickets wieder oeffnen"),
    ModerationActionSpec("ticket_status", "Ticket Status", "Ticket-Status aendern"),
    ModerationActionSpec("ticket_priority", "Ticket Priority", "Ticket-Prioritaet aendern"),
    ModerationActionSpec("ticket_escalate", "Ticket Escalate", "Tickets eskalieren"),
    ModerationActionSpec("ticket_category", "Ticket Category", "Ticket-Kategorie wechseln"),
    ModerationActionSpec("ticket_transcript", "Ticket Transcript", "Ticket-Transcript erstellen"),
    ModerationActionSpec("ticket_forward", "Ticket Forward", "Tickets weiterleiten"),
    ModerationActionSpec("ticket_support_panel", "Ticket Support Panel", "Support-Panel senden"),
    ModerationActionSpec("ticket_snippet_list", "Ticket Snippet List", "Ticket-Snippets anzeigen"),
    ModerationActionSpec("ticket_snippet_send", "Ticket Snippet Send", "Ticket-Snippets senden"),
    ModerationActionSpec("giveaway_create", "Giveaway Create", "Giveaways erstellen"),
    ModerationActionSpec("giveaway_reroll", "Giveaway Reroll", "Giveaway-Gewinner neu auslosen"),
    ModerationActionSpec("poll_create", "Poll Create", "Umfragen erstellen"),
    ModerationActionSpec("poll_close", "Poll Close", "Umfragen schliessen"),
    ModerationActionSpec("parliament_start_vote", "Parliament Start Vote", "Parlaments-Votum starten"),
    ModerationActionSpec("parliament_stop_vote", "Parliament Stop Vote", "Parlaments-Votum stoppen"),
    ModerationActionSpec("parliament_panel", "Parliament Panel", "Parlaments-Panel aktualisieren"),
    ModerationActionSpec("parliament_party_panel", "Parliament Party Panel", "Partei-Panel senden"),
    ModerationActionSpec("parliament_party_approve", "Parliament Party Approve", "Parteien genehmigen"),
    ModerationActionSpec("parliament_party_reject", "Parliament Party Reject", "Parteien ablehnen"),
    ModerationActionSpec("parliament_party_list", "Parliament Party List", "Parteien anzeigen"),
    ModerationActionSpec("seelsorge_setup", "Seelsorge Setup", "Seelsorge konfigurieren"),
    ModerationActionSpec("seelsorge_panel", "Seelsorge Panel", "Seelsorge-Panel senden"),
    ModerationActionSpec("seelsorge_close", "Seelsorge Close", "Seelsorge-Threads schliessen"),
    ModerationActionSpec("seelsorge_open", "Seelsorge Open", "Seelsorge-Threads oeffnen"),
    ModerationActionSpec("seelsorge_delete", "Seelsorge Delete", "Seelsorge-Threads loeschen"),
    ModerationActionSpec("seelsorge_who", "Seelsorge Who", "Seelsorge-Ersteller anzeigen"),
    ModerationActionSpec("wort_setup", "Wort Setup", "Wort-zum-Sonntag konfigurieren"),
    ModerationActionSpec("wort_panel", "Wort Panel", "Wort-zum-Sonntag-Panel senden"),
    ModerationActionSpec("wort_accept", "Wort Accept", "Weisheiten annehmen"),
    ModerationActionSpec("wort_reject", "Wort Reject", "Weisheiten ablehnen"),
    ModerationActionSpec("roles_sync", "Roles Sync", "Auto-Rollen synchronisieren", "manage_roles"),
    ModerationActionSpec("roles_rescan", "Roles Rescan", "Rollen/Erfolge neu pruefen", "manage_roles"),
    ModerationActionSpec("roles_mass_add", "Roles Mass Add", "Rolle an alle vergeben", "manage_roles"),
    ModerationActionSpec("roles_panel_send", "Roles Panel Send", "Rollen-Info-Panel senden", "manage_guild"),
    ModerationActionSpec("roles_debug", "Roles Debug", "Rollen-Info debuggen", "manage_guild"),
    ModerationActionSpec("flag_setup", "Flag Setup", "Flaggenquiz konfigurieren", "manage_channels"),
    ModerationActionSpec("flag_panel", "Flag Panel", "Flaggen-Panel aktualisieren", "manage_channels"),
    ModerationActionSpec("flag_kingrole", "Flag Kingrole", "Flaggenkoenig-Rolle setzen", "manage_roles"),
    ModerationActionSpec("flag_start", "Flag Start", "Flaggenrunde starten", "manage_channels"),
    ModerationActionSpec("news_send", "News Send", "Neueste News senden", "manage_guild"),
    ModerationActionSpec("youtube_send", "YouTube Send", "Neueste YouTube-News senden", "manage_guild"),
    ModerationActionSpec("nebu_send", "Nebu Send", "Nebuliton-Sponsorpanel senden", "manage_guild"),
    ModerationActionSpec("guide_build", "Guide Build", "Server-Guide bauen", "manage_guild"),
)

MODERATION_ACTION_MAP: dict[str, ModerationActionSpec] = {spec.key: spec for spec in MODERATION_ACTIONS}
MODERATION_ACTION_KEYS: dict[str, str] = {_keyify(spec.key): spec.key for spec in MODERATION_ACTIONS}
_ACTION_KEY_ALIASES: dict[str, str] = {
    _keyify("parlament_vote_start"): "parliament_start_vote",
    _keyify("parlament_vote_stop"): "parliament_stop_vote",
    _keyify("parlament_panel"): "parliament_panel",
    _keyify("parlament_party_panel"): "parliament_party_panel",
    _keyify("parlament_party_approve"): "parliament_party_approve",
    _keyify("parlament_party_reject"): "parliament_party_reject",
    _keyify("parlament_party_list"): "parliament_party_list",
}

_PERMISSION_FLAG_ALIASES: dict[str, str] = {
    "timeout": "moderate_members",
    "timeouts": "moderate_members",
    "mute": "moderate_members",
    "moderate": "moderate_members",
    "kick": "kick_members",
    "ban": "ban_members",
    "unban": "ban_members",
    "purge": "manage_messages",
    "clear": "manage_messages",
    "slowmode": "manage_channels",
    "lock": "manage_channels",
    "unlock": "manage_channels",
    "nick": "manage_nicknames",
    "role": "manage_roles",
    "roles": "manage_roles",
    "admin": "administrator",
}
_PERMISSION_FLAG_KEYS: dict[str, str] = {_keyify(str(flag)): str(flag) for flag in discord.Permissions.VALID_FLAGS}


class PermissionService:
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db

    @staticmethod
    def permission_flags() -> list[str]:
        return sorted(str(flag) for flag in discord.Permissions.VALID_FLAGS)

    @staticmethod
    def permission_label(permission: str | None) -> str:
        if not permission:
            return "Keine"
        return str(permission).replace("_", " ").title()

    @staticmethod
    def enabled_permission_flags(permissions: discord.Permissions) -> list[str]:
        return sorted(str(flag) for flag, enabled in permissions if enabled)

    @staticmethod
    def managed_member_role_name(user_id: int) -> str:
        return f"{PERSONAL_PERMISSION_ROLE_PREFIX}{int(user_id)}"

    @staticmethod
    def _coerce_id_set(raw) -> set[int]:
        if isinstance(raw, (int, str)):
            raw = [raw]
        elif not isinstance(raw, (list, tuple, set)):
            return set()
        out: set[int] = set()
        for item in raw:
            try:
                value = int(item)
            except Exception:
                continue
            if value > 0:
                out.add(value)
        return out

    def normalize_permission_flag(self, raw: str | None) -> str | None:
        key = _keyify(raw)
        if not key:
            return None
        if key in _PERMISSION_FLAG_ALIASES:
            return _PERMISSION_FLAG_ALIASES[key]
        return _PERMISSION_FLAG_KEYS.get(key)

    def normalize_action_key(self, raw: str | None) -> str | None:
        key = _keyify(raw)
        if not key:
            return None
        return MODERATION_ACTION_KEYS.get(key) or _ACTION_KEY_ALIASES.get(key)

    def get_action_spec(self, action: str | None) -> ModerationActionSpec | None:
        key = self.normalize_action_key(action)
        if not key:
            return None
        return MODERATION_ACTION_MAP.get(key)

    def action_role_ids(self, guild_id: int, action: str | None) -> set[int]:
        spec = self.get_action_spec(action)
        if not spec:
            return set()
        values = self._coerce_id_set(self.settings.get_guild(guild_id, f"moderation.permissions.{spec.key}_role_ids", []) or [])
        for legacy_key in self._legacy_action_keys(spec.key):
            values.update(
                self._coerce_id_set(
                    self.settings.get_guild(guild_id, f"moderation.permissions.{legacy_key}_role_ids", []) or []
                )
            )
        return values

    def action_user_ids(self, guild_id: int, action: str | None) -> set[int]:
        spec = self.get_action_spec(action)
        if not spec:
            return set()
        values = self._coerce_id_set(self.settings.get_guild(guild_id, f"moderation.permissions.{spec.key}_user_ids", []) or [])
        for legacy_key in self._legacy_action_keys(spec.key):
            values.update(
                self._coerce_id_set(
                    self.settings.get_guild(guild_id, f"moderation.permissions.{legacy_key}_user_ids", []) or []
                )
            )
        return values

    @staticmethod
    def _legacy_action_keys(action: str) -> tuple[str, ...]:
        legacy = {
            "parliament_start_vote": ("parlament_vote_start",),
            "parliament_stop_vote": ("parlament_vote_stop",),
            "parliament_panel": ("parlament_panel",),
            "parliament_party_panel": ("parlament_party_panel",),
            "parliament_party_approve": ("parlament_party_approve",),
            "parliament_party_reject": ("parlament_party_reject",),
            "parliament_party_list": ("parlament_party_list",),
        }
        return legacy.get(str(action), ())

    async def set_action_target(self, guild_id: int, action: str, target_type: str, target_id: int, enabled: bool) -> tuple[str | None, bool, set[int]]:
        spec = self.get_action_spec(action)
        if not spec:
            return None, False, set()
        if target_type not in {"role", "user"}:
            return spec.key, False, set()
        path = f"moderation.permissions.{spec.key}_{target_type}_ids"
        ids = self.action_role_ids(guild_id, spec.key) if target_type == "role" else self.action_user_ids(guild_id, spec.key)
        before = set(ids)
        if enabled:
            ids.add(int(target_id))
        else:
            ids.discard(int(target_id))
        changed = ids != before
        await self.settings.set_guild_override(self.db, guild_id, path, sorted(ids))
        return spec.key, changed, ids

    def member_has_action_access(self, member: discord.Member, action: str | None) -> bool:
        if member.guild_permissions.administrator:
            return True
        spec = self.get_action_spec(action)
        if not spec:
            return False
        role_ids = self.action_role_ids(member.guild.id, spec.key)
        user_ids = self.action_user_ids(member.guild.id, spec.key)
        if role_ids or user_ids:
            return member.id in user_ids or any(role.id in role_ids for role in member.roles)
        return is_staff(self.settings, member)

    def action_required_permission(self, action: str | None) -> str | None:
        spec = self.get_action_spec(action)
        return spec.discord_permission if spec else None

    def missing_action_permission(self, member: discord.Member, action: str | None) -> str | None:
        flag = self.action_required_permission(action)
        if not flag:
            return None
        if getattr(member.guild_permissions, flag, False):
            return None
        return flag

    def action_error(self, member: discord.Member, action: str | None) -> str | None:
        if not self.member_has_action_access(member, action):
            return "Keine Rechte."
        missing = self.missing_action_permission(member, action)
        if missing:
            return f"Dir fehlt `{self.permission_label(missing)}`."
        return None

    @staticmethod
    def _bot_member(guild: discord.Guild) -> discord.Member | None:
        me = getattr(guild, "me", None)
        if isinstance(me, discord.Member):
            return me
        return None

    def validate_manageable_role(self, actor: discord.Member, role: discord.Role) -> str | None:
        guild = actor.guild
        bot_member = self._bot_member(guild)
        if role.managed:
            return "Die Rolle wird von Discord oder einer Integration verwaltet."
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            return "Dem Bot fehlt `Manage Roles`."
        if role != guild.default_role and actor.id != guild.owner_id and role >= actor.top_role:
            return "Du kannst nur Rollen unter deiner hoechsten Rolle aendern."
        if role != guild.default_role and role >= bot_member.top_role:
            return "Die Rolle liegt ueber der hoechsten Bot-Rolle."
        return None

    def validate_manageable_member(self, actor: discord.Member, target: discord.Member) -> str | None:
        guild = actor.guild
        bot_member = self._bot_member(guild)
        if not bot_member or not bot_member.guild_permissions.manage_roles:
            return "Dem Bot fehlt `Manage Roles`."
        if target.id == guild.owner_id and actor.id != guild.owner_id:
            return "Der Server-Owner kann nicht verwaltet werden."
        if actor.id != guild.owner_id and target.id != actor.id and target.top_role >= actor.top_role:
            return "Der User liegt auf oder ueber deiner Rollen-Hierarchie."
        if target.id != guild.owner_id and target.top_role >= bot_member.top_role:
            return "Der User liegt auf oder ueber der Bot-Rolle."
        return None

    def get_member_managed_role(self, guild: discord.Guild, user_id: int) -> discord.Role | None:
        name = self.managed_member_role_name(user_id)
        for role in guild.roles:
            if role.name == name:
                return role
        return None

    async def ensure_member_managed_role(
        self,
        actor: discord.Member,
        target: discord.Member,
        reason: str | None = None,
    ) -> tuple[discord.Role | None, str | None]:
        err = self.validate_manageable_member(actor, target)
        if err:
            return None, err
        role = self.get_member_managed_role(target.guild, target.id)
        if role is None:
            try:
                role = await target.guild.create_role(
                    name=self.managed_member_role_name(target.id),
                    permissions=discord.Permissions.none(),
                    mentionable=False,
                    hoist=False,
                    reason=reason or f"permission-role:create:{target.id}",
                )
            except Exception as exc:
                return None, f"{type(exc).__name__}: {exc}"
        err = self.validate_manageable_role(actor, role)
        if err:
            return None, err
        if role not in target.roles:
            try:
                await target.add_roles(role, reason=reason or f"permission-role:assign:{target.id}")
            except Exception as exc:
                return None, f"{type(exc).__name__}: {exc}"
        return role, None

    async def set_role_permission(
        self,
        actor: discord.Member,
        role: discord.Role,
        permission: str,
        enabled: bool,
        reason: str | None = None,
    ) -> tuple[bool, str | None, bool]:
        flag = self.normalize_permission_flag(permission)
        if not flag:
            return False, "Unbekannte Permission.", False
        err = self.validate_manageable_role(actor, role)
        if err:
            return False, err, False
        perms = discord.Permissions(role.permissions.value)
        before = bool(getattr(perms, flag, False))
        perms.update(**{flag: bool(enabled)})
        changed = perms.value != role.permissions.value
        if changed:
            try:
                await role.edit(permissions=perms, reason=reason or f"permission:{'grant' if enabled else 'revoke'}:{flag}")
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}", False
        return True, None, before != bool(enabled)

    async def set_member_permission(
        self,
        actor: discord.Member,
        target: discord.Member,
        permission: str,
        enabled: bool,
        reason: str | None = None,
    ) -> tuple[bool, str | None, discord.Role | None, bool]:
        flag = self.normalize_permission_flag(permission)
        if not flag:
            return False, "Unbekannte Permission.", None, False
        if enabled:
            role, err = await self.ensure_member_managed_role(actor, target, reason=reason)
            if err:
                return False, err, None, False
        else:
            err = self.validate_manageable_member(actor, target)
            if err:
                return False, err, None, False
            role = self.get_member_managed_role(target.guild, target.id)
            if role is None:
                return True, None, None, False
            err = self.validate_manageable_role(actor, role)
            if err:
                return False, err, role, False

        perms = discord.Permissions(role.permissions.value)
        before = bool(getattr(perms, flag, False))
        perms.update(**{flag: bool(enabled)})
        changed = perms.value != role.permissions.value
        if changed:
            try:
                await role.edit(permissions=perms, reason=reason or f"permission:{'grant' if enabled else 'revoke'}:{flag}")
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}", role, False

        if enabled and role not in target.roles:
            try:
                await target.add_roles(role, reason=reason or f"permission-role:assign:{target.id}")
            except Exception as exc:
                return False, f"{type(exc).__name__}: {exc}", role, False

        if not enabled and perms.value == 0:
            try:
                if role in target.roles:
                    await target.remove_roles(role, reason=reason or f"permission-role:cleanup:{target.id}")
            except Exception:
                pass
            try:
                if not role.members:
                    await role.delete(reason=reason or f"permission-role:delete:{target.id}")
            except Exception:
                pass

        return True, None, role, before != bool(enabled)
