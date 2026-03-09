from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.core.perms import is_staff
from bot.modules.moderation.services.mod_service import ModerationService
from bot.modules.moderation.services.permission_service import MODERATION_ACTIONS, PermissionService
from bot.modules.moderation.formatting.moderation_embeds import build_channel_access_embed


async def _ephemeral(interaction: discord.Interaction, text: str):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(text, ephemeral=True)
        else:
            await interaction.followup.send(text, ephemeral=True)
    except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
        try:
            await interaction.followup.send(text, ephemeral=True)
        except Exception:
            pass


async def _defer(interaction: discord.Interaction):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
    except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
        pass


async def _ephemeral_embed(interaction: discord.Interaction, embed: discord.Embed):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(embed=embed, ephemeral=True)
    except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
        try:
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception:
            pass


class ModerationCommands(commands.Cog):
    permission = app_commands.Group(name="permission", description="🔐 𑁉 Permissions verwalten")

    def __init__(self, bot):
        self.bot = bot
        self.service = ModerationService(bot, bot.settings, bot.db, getattr(bot, "forum_logs", None))
        self.permission_service = PermissionService(bot.settings, bot.db)

    def _embed_color(self, guild: discord.Guild | None) -> int:
        value = self.bot.settings.get_guild(guild.id, "design.accent_color", "#B16B91") if guild else self.bot.settings.get("design.accent_color", "#B16B91")
        try:
            return int(str(value).strip().replace("#", ""), 16)
        except Exception:
            return 0xB16B91

    def _build_embed(self, guild: discord.Guild, actor: discord.Member, title: str, description: str) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=self._embed_color(guild))
        embed.set_author(name=actor.display_name, icon_url=actor.display_avatar.url)
        bot_member = getattr(guild, "me", None)
        if bot_member:
            embed.set_footer(text=bot_member.display_name, icon_url=bot_member.display_avatar.url)
        return embed

    def _need_guild(self, interaction: discord.Interaction):
        return interaction.guild and isinstance(interaction.user, discord.Member)

    def _need_ctx(self, ctx: commands.Context) -> bool:
        return bool(ctx.guild and isinstance(ctx.author, discord.Member))

    async def _ctx_reply(self, ctx: commands.Context, text: str):
        try:
            await ctx.reply(text, mention_author=False)
        except Exception:
            try:
                await ctx.send(text)
            except Exception:
                pass

    def _cfg_role_ids(self, guild_id: int, action: str) -> set[int]:
        return self.permission_service.action_role_ids(guild_id, action)

    def _cfg_user_ids(self, guild_id: int, action: str) -> set[int]:
        return self.permission_service.action_user_ids(guild_id, action)

    def _has_action_access(self, member: discord.Member, action: str) -> bool:
        return self.permission_service.member_has_action_access(member, action)

    def _action_error(self, member: discord.Member, action: str) -> str | None:
        return self.permission_service.action_error(member, action)

    def _can_manage_discord_permissions(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        return bool(member.guild_permissions.manage_roles)

    def _can_manage_action_configs(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        return is_staff(self.bot.settings, member) and member.guild_permissions.manage_guild

    def _resolve_subject(
        self,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
    ) -> tuple[str | None, discord.Member | discord.Role | None, str | None]:
        if bool(user) == bool(role):
            return None, None, "Bitte gib genau einen User oder genau eine Rolle an."
        if user is not None:
            return "user", user, None
        return "role", role, None

    def _namespace_subject(
        self,
        interaction: discord.Interaction,
    ) -> tuple[str | None, discord.Member | discord.Role | None]:
        namespace = getattr(interaction, "namespace", None)
        if namespace is None:
            return None, None
        user = getattr(namespace, "user", None)
        role = getattr(namespace, "role", None)
        if isinstance(user, discord.Member):
            return "user", user
        if isinstance(role, discord.Role):
            return "role", role
        return None, None

    @staticmethod
    def _truncate_choice(name: str, limit: int = 100) -> str:
        text = str(name)
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def _action_status_label(
        self,
        guild: discord.Guild,
        subject_type: str | None,
        subject: discord.Member | discord.Role | None,
        action: str,
    ) -> str | None:
        if not subject_type or subject is None:
            return None
        role_ids = self._cfg_role_ids(guild.id, action)
        user_ids = self._cfg_user_ids(guild.id, action)
        if subject_type == "role" and isinstance(subject, discord.Role):
            return "schon gesetzt" if int(subject.id) in role_ids else "noch frei"
        if subject_type == "user" and isinstance(subject, discord.Member):
            if int(subject.id) in user_ids:
                return "schon direkt"
            if any(role.id in role_ids for role in subject.roles):
                return "schon via Rolle"
            if not role_ids and not user_ids and is_staff(self.bot.settings, subject):
                return "via Staff"
            return "noch frei"
        return None

    def _permission_status_label(
        self,
        guild: discord.Guild,
        subject_type: str | None,
        subject: discord.Member | discord.Role | None,
        permission: str,
    ) -> str | None:
        if not subject_type or subject is None:
            return None
        if subject_type == "role" and isinstance(subject, discord.Role):
            return "schon aktiv" if getattr(subject.permissions, permission, False) else "noch frei"
        if subject_type == "user" and isinstance(subject, discord.Member):
            managed_role = self.permission_service.get_member_managed_role(guild, subject.id)
            if managed_role and getattr(managed_role.permissions, permission, False):
                return "schon direkt"
            if getattr(subject.guild_permissions, permission, False):
                return "schon via Rolle"
            return "noch frei"
        return None

    def _format_flag_list(self, flags: list[str], limit: int = 16) -> str:
        if not flags:
            return "—"
        parts = [f"`{flag}`" for flag in flags[:limit]]
        if len(flags) > limit:
            parts.append(f"`+{len(flags) - limit}` weitere")
        return ", ".join(parts)

    def _format_subject_list(self, guild: discord.Guild, ids: set[int], subject_type: str, limit: int = 12) -> str:
        if not ids:
            return "—"
        ordered = sorted(int(value) for value in ids)
        items: list[str] = []
        for value in ordered[:limit]:
            if subject_type == "role":
                role = guild.get_role(value)
                items.append(role.mention if role else f"`{value}`")
            else:
                items.append(f"<@{value}>")
        if len(ordered) > limit:
            items.append(f"`+{len(ordered) - limit}` weitere")
        return ", ".join(items)

    def _build_permission_state_embed(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        title: str,
        subject_label: str,
        effective_flags: list[str],
        direct_flags: list[str] | None = None,
        note: str | None = None,
    ) -> discord.Embed:
        lines = [subject_label, f"Aktive Rechte: **{len(effective_flags)}**"]
        if note:
            lines.append(note)
        embed = self._build_embed(guild, actor, title, "\n".join(lines))
        embed.add_field(name="Aktive Rechte", value=self._format_flag_list(effective_flags), inline=False)
        if direct_flags is not None:
            embed.add_field(name="Direkt verwaltet", value=self._format_flag_list(direct_flags), inline=False)
        return embed

    def _parse_lock_mode(self, raw: str | None) -> str:
        x = str(raw or "all").strip().lower()
        if x in {"s", "send", "write", "schreiben", "w"}:
            return "send"
        if x in {"v", "view", "see", "sehen", "read", "r"}:
            return "view"
        return "all"

    async def _apply_channel_lock(
        self,
        guild: discord.Guild,
        actor: discord.Member,
        channel: discord.TextChannel,
        mode: str,
        locked: bool,
    ) -> tuple[bool, str | None]:
        overwrite = channel.overwrites_for(guild.default_role)
        if mode in {"send", "all"}:
            overwrite.send_messages = False if locked else None
        if mode in {"view", "all"}:
            overwrite.view_channel = False if locked else None
        try:
            await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=f"moderation:{'lock' if locked else 'unlock'}:{mode}")
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"
        try:
            if self.service.forum_logs:
                emb = build_channel_access_embed(self.bot.settings, guild, actor, channel, mode, locked)
                await self.service.forum_logs.emit(guild, "punishments", emb)
        except Exception:
            pass
        return True, None

    @permission.command(name="show", description="📋 𑁉 Rechte eines Users oder einer Rolle anzeigen")
    @app_commands.describe(user="Zieluser", role="Zielrolle")
    async def permission_show(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
    ):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_discord_permissions(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")
        subject_type, subject, err = self._resolve_subject(user=user, role=role)
        if err:
            return await _ephemeral(interaction, err)
        if subject_type == "user" and isinstance(subject, discord.Member):
            managed_role = self.permission_service.get_member_managed_role(interaction.guild, subject.id)
            direct_flags = self.permission_service.enabled_permission_flags(managed_role.permissions) if managed_role else []
            effective_flags = self.permission_service.enabled_permission_flags(subject.guild_permissions)
            note = f"Starry-Rolle: {managed_role.mention}" if managed_role else "Starry-Rolle: keine direkte User-Rolle"
            embed = self._build_permission_state_embed(
                interaction.guild,
                interaction.user,
                "🔐 𑁉 USER-PERMISSIONS",
                f"User: {subject.mention} (`{subject.id}`)",
                effective_flags,
                direct_flags=direct_flags,
                note=note,
            )
            return await _ephemeral_embed(interaction, embed)

        assert isinstance(subject, discord.Role)
        flags = self.permission_service.enabled_permission_flags(subject.permissions)
        embed = self._build_permission_state_embed(
            interaction.guild,
            interaction.user,
            "🔐 𑁉 ROLE-PERMISSIONS",
            f"Rolle: {subject.mention} (`{subject.id}`)",
            flags,
        )
        await _ephemeral_embed(interaction, embed)

    @permission.command(name="grant", description="➕ 𑁉 Discord-Permission an User oder Rolle vergeben")
    @app_commands.describe(permission="Discord-Permission", user="Zieluser", role="Zielrolle", reason="Optionaler Audit-Log-Grund")
    async def permission_grant(
        self,
        interaction: discord.Interaction,
        permission: str,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
        reason: str | None = None,
    ):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_discord_permissions(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")
        subject_type, subject, err = self._resolve_subject(user=user, role=role)
        if err:
            return await _ephemeral(interaction, err)
        flag = self.permission_service.normalize_permission_flag(permission)
        if not flag:
            return await _ephemeral(interaction, "Unbekannte Permission.")

        if subject_type == "user" and isinstance(subject, discord.Member):
            ok, err, managed_role, changed = await self.permission_service.set_member_permission(
                interaction.user,
                subject,
                flag,
                True,
                reason=reason,
            )
            if not ok:
                return await _ephemeral(interaction, f"Permission konnte nicht vergeben werden: {err}")
            direct_flags = self.permission_service.enabled_permission_flags(managed_role.permissions) if managed_role else []
            effective_flags = self.permission_service.enabled_permission_flags(subject.guild_permissions)
            note = f"{self.permission_service.permission_label(flag)} wurde {'gesetzt' if changed else 'bereits gehalten'}."
            if managed_role:
                note += f" Starry-Rolle: {managed_role.mention}"
            embed = self._build_permission_state_embed(
                interaction.guild,
                interaction.user,
                "➕ 𑁉 USER-PERMISSION",
                f"User: {subject.mention} (`{subject.id}`)",
                effective_flags,
                direct_flags=direct_flags,
                note=note,
            )
            return await _ephemeral_embed(interaction, embed)

        assert isinstance(subject, discord.Role)
        ok, err, changed = await self.permission_service.set_role_permission(
            interaction.user,
            subject,
            flag,
            True,
            reason=reason,
        )
        if not ok:
            return await _ephemeral(interaction, f"Permission konnte nicht vergeben werden: {err}")
        flags = self.permission_service.enabled_permission_flags(subject.permissions)
        embed = self._build_permission_state_embed(
            interaction.guild,
            interaction.user,
            "➕ 𑁉 ROLE-PERMISSION",
            f"Rolle: {subject.mention} (`{subject.id}`)",
            flags,
            note=f"{self.permission_service.permission_label(flag)} wurde {'gesetzt' if changed else 'bereits gehalten'}.",
        )
        await _ephemeral_embed(interaction, embed)

    @permission.command(name="revoke", description="➖ 𑁉 Discord-Permission von User oder Rolle entfernen")
    @app_commands.describe(permission="Discord-Permission", user="Zieluser", role="Zielrolle", reason="Optionaler Audit-Log-Grund")
    async def permission_revoke(
        self,
        interaction: discord.Interaction,
        permission: str,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
        reason: str | None = None,
    ):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_discord_permissions(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")
        subject_type, subject, err = self._resolve_subject(user=user, role=role)
        if err:
            return await _ephemeral(interaction, err)
        flag = self.permission_service.normalize_permission_flag(permission)
        if not flag:
            return await _ephemeral(interaction, "Unbekannte Permission.")

        if subject_type == "user" and isinstance(subject, discord.Member):
            ok, err, managed_role, changed = await self.permission_service.set_member_permission(
                interaction.user,
                subject,
                flag,
                False,
                reason=reason,
            )
            if not ok:
                return await _ephemeral(interaction, f"Permission konnte nicht entfernt werden: {err}")
            current_role = self.permission_service.get_member_managed_role(interaction.guild, subject.id)
            direct_flags = self.permission_service.enabled_permission_flags(current_role.permissions) if current_role else []
            effective_flags = self.permission_service.enabled_permission_flags(subject.guild_permissions)
            note = f"{self.permission_service.permission_label(flag)} wurde {'entfernt' if changed else 'nicht direkt gefunden'}."
            if current_role:
                note += f" Starry-Rolle: {current_role.mention}"
            embed = self._build_permission_state_embed(
                interaction.guild,
                interaction.user,
                "➖ 𑁉 USER-PERMISSION",
                f"User: {subject.mention} (`{subject.id}`)",
                effective_flags,
                direct_flags=direct_flags,
                note=note,
            )
            return await _ephemeral_embed(interaction, embed)

        assert isinstance(subject, discord.Role)
        ok, err, changed = await self.permission_service.set_role_permission(
            interaction.user,
            subject,
            flag,
            False,
            reason=reason,
        )
        if not ok:
            return await _ephemeral(interaction, f"Permission konnte nicht entfernt werden: {err}")
        flags = self.permission_service.enabled_permission_flags(subject.permissions)
        embed = self._build_permission_state_embed(
            interaction.guild,
            interaction.user,
            "➖ 𑁉 ROLE-PERMISSION",
            f"Rolle: {subject.mention} (`{subject.id}`)",
            flags,
            note=f"{self.permission_service.permission_label(flag)} wurde {'entfernt' if changed else 'nicht direkt gefunden'}.",
        )
        await _ephemeral_embed(interaction, embed)

    @permission.command(name="mod-show", description="🛡️ 𑁉 Bot-Command-Freigaben anzeigen")
    @app_commands.describe(action="Optionale Bot-Aktion")
    async def permission_mod_show(self, interaction: discord.Interaction, action: str | None = None):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_action_configs(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")

        if action:
            spec = self.permission_service.get_action_spec(action)
            if not spec:
                return await _ephemeral(interaction, "Unbekannte Moderations-Aktion.")
            role_ids = self._cfg_role_ids(interaction.guild.id, spec.key)
            user_ids = self._cfg_user_ids(interaction.guild.id, spec.key)
            native = self.permission_service.action_required_permission(spec.key)
            mode = "Explizite Freigabe aktiv" if role_ids or user_ids else "Fallback auf Staff-/Support-Rollen"
            desc = (
                f"Aktion: **{spec.label}** (`{spec.key}`)\n"
                f"Command: {spec.description}\n"
                f"Discord-Permission: `{native or 'keine zusaetzliche'}`\n"
                f"Modus: {mode}"
            )
            embed = self._build_embed(interaction.guild, interaction.user, "🛡️ 𑁉 BOT-PERMISSIONS", desc)
            embed.add_field(name="Freigegebene User", value=self._format_subject_list(interaction.guild, user_ids, "user"), inline=False)
            embed.add_field(name="Freigegebene Rollen", value=self._format_subject_list(interaction.guild, role_ids, "role"), inline=False)
            return await _ephemeral_embed(interaction, embed)

        lines: list[str] = []
        for spec in MODERATION_ACTIONS:
            user_ids = self._cfg_user_ids(interaction.guild.id, spec.key)
            role_ids = self._cfg_role_ids(interaction.guild.id, spec.key)
            native = self.permission_service.action_required_permission(spec.key)
            lines.append(
                f"`{spec.key}` • User **{len(user_ids)}** • Rollen **{len(role_ids)}** • Discord: `{native or '—'}`"
            )
        embed = self._build_embed(
            interaction.guild,
            interaction.user,
            "🛡️ 𑁉 MOD-PERMISSIONS",
            "\n".join(lines) if lines else "Keine Bot-Aktionen gefunden.",
        )
        await _ephemeral_embed(interaction, embed)

    @permission.command(name="mod-grant", description="✅ 𑁉 Bot-Command fuer User oder Rolle freigeben")
    @app_commands.describe(
        action="Bot-Aktion",
        user="Zieluser",
        role="Zielrolle",
        also_discord_permission="Setzt falls noetig auch die native Discord-Permission",
        reason="Optionaler Audit-Log-Grund",
    )
    async def permission_mod_grant(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
        also_discord_permission: bool = True,
        reason: str | None = None,
    ):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_action_configs(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")
        subject_type, subject, err = self._resolve_subject(user=user, role=role)
        if err:
            return await _ephemeral(interaction, err)
        spec = self.permission_service.get_action_spec(action)
        if not spec:
            return await _ephemeral(interaction, "Unbekannte Bot-Aktion.")

        native = self.permission_service.action_required_permission(spec.key)
        native_note = "Discord-Permission unveraendert."
        if also_discord_permission and native:
            if subject_type == "user" and isinstance(subject, discord.Member):
                ok, native_err, _managed_role, _changed = await self.permission_service.set_member_permission(
                    interaction.user,
                    subject,
                    native,
                    True,
                    reason=reason,
                )
            else:
                assert isinstance(subject, discord.Role)
                ok, native_err, _changed = await self.permission_service.set_role_permission(
                    interaction.user,
                    subject,
                    native,
                    True,
                    reason=reason,
                )
            if not ok:
                return await _ephemeral(interaction, f"Native Discord-Permission konnte nicht gesetzt werden: {native_err}")
            native_note = f"Discord-Permission `{native}` wurde mitgesetzt."

        _, _, _ = await self.permission_service.set_action_target(
            interaction.guild.id,
            spec.key,
            subject_type,
            int(subject.id),
            True,
        )
        role_ids = self._cfg_role_ids(interaction.guild.id, spec.key)
        user_ids = self._cfg_user_ids(interaction.guild.id, spec.key)
        subject_label = f"User: {subject.mention} (`{subject.id}`)" if subject_type == "user" else f"Rolle: {subject.mention} (`{subject.id}`)"
        embed = self._build_embed(
            interaction.guild,
            interaction.user,
            "✅ 𑁉 BOT-PERMISSION",
            (
                f"{subject_label}\n"
                f"Aktion: **{spec.label}** (`{spec.key}`)\n"
                f"{native_note}"
            ),
        )
        embed.add_field(name="Freigegebene User", value=self._format_subject_list(interaction.guild, user_ids, "user"), inline=False)
        embed.add_field(name="Freigegebene Rollen", value=self._format_subject_list(interaction.guild, role_ids, "role"), inline=False)
        await _ephemeral_embed(interaction, embed)

    @permission.command(name="mod-revoke", description="🚫 𑁉 Bot-Command fuer User oder Rolle entfernen")
    @app_commands.describe(
        action="Bot-Aktion",
        user="Zieluser",
        role="Zielrolle",
        remove_discord_permission="Entfernt falls noetig auch die native Discord-Permission",
        reason="Optionaler Audit-Log-Grund",
    )
    async def permission_mod_revoke(
        self,
        interaction: discord.Interaction,
        action: str,
        user: discord.Member | None = None,
        role: discord.Role | None = None,
        remove_discord_permission: bool = False,
        reason: str | None = None,
    ):
        if not self._need_guild(interaction):
            return
        if not self._can_manage_action_configs(interaction.user):
            return await _ephemeral(interaction, "Keine Rechte.")
        subject_type, subject, err = self._resolve_subject(user=user, role=role)
        if err:
            return await _ephemeral(interaction, err)
        spec = self.permission_service.get_action_spec(action)
        if not spec:
            return await _ephemeral(interaction, "Unbekannte Bot-Aktion.")

        native = self.permission_service.action_required_permission(spec.key)
        native_note = "Discord-Permission unveraendert."
        if remove_discord_permission and native:
            if subject_type == "user" and isinstance(subject, discord.Member):
                ok, native_err, _managed_role, _changed = await self.permission_service.set_member_permission(
                    interaction.user,
                    subject,
                    native,
                    False,
                    reason=reason,
                )
            else:
                assert isinstance(subject, discord.Role)
                ok, native_err, _changed = await self.permission_service.set_role_permission(
                    interaction.user,
                    subject,
                    native,
                    False,
                    reason=reason,
                )
            if not ok:
                return await _ephemeral(interaction, f"Native Discord-Permission konnte nicht entfernt werden: {native_err}")
            native_note = f"Discord-Permission `{native}` wurde ebenfalls entfernt."

        _, _, _ = await self.permission_service.set_action_target(
            interaction.guild.id,
            spec.key,
            subject_type,
            int(subject.id),
            False,
        )
        role_ids = self._cfg_role_ids(interaction.guild.id, spec.key)
        user_ids = self._cfg_user_ids(interaction.guild.id, spec.key)
        subject_label = f"User: {subject.mention} (`{subject.id}`)" if subject_type == "user" else f"Rolle: {subject.mention} (`{subject.id}`)"
        embed = self._build_embed(
            interaction.guild,
            interaction.user,
            "🚫 𑁉 BOT-PERMISSION",
            (
                f"{subject_label}\n"
                f"Aktion: **{spec.label}** (`{spec.key}`)\n"
                f"{native_note}"
            ),
        )
        embed.add_field(name="Freigegebene User", value=self._format_subject_list(interaction.guild, user_ids, "user"), inline=False)
        embed.add_field(name="Freigegebene Rollen", value=self._format_subject_list(interaction.guild, role_ids, "role"), inline=False)
        await _ephemeral_embed(interaction, embed)

    @permission_grant.autocomplete("permission")
    @permission_revoke.autocomplete("permission")
    async def permission_flag_autocomplete(self, interaction: discord.Interaction, current: str):
        term = str(current or "").strip().lower()
        subject_type, subject = self._namespace_subject(interaction)
        out: list[app_commands.Choice[str]] = []
        for flag in self.permission_service.permission_flags():
            label = self.permission_service.permission_label(flag)
            status = self._permission_status_label(interaction.guild, subject_type, subject, flag) if interaction.guild else None
            hay = f"{flag} {label} {status or ''}".lower()
            if term and term not in hay:
                continue
            suffix = f" • {status}" if status else ""
            out.append(app_commands.Choice(name=self._truncate_choice(f"{label} ({flag}){suffix}"), value=flag))
        if subject_type and subject is not None:
            out.sort(key=lambda choice: ("schon" not in choice.name and "via" not in choice.name, choice.name.lower()))
        return out[:25]

    @permission_mod_show.autocomplete("action")
    @permission_mod_grant.autocomplete("action")
    @permission_mod_revoke.autocomplete("action")
    async def permission_action_autocomplete(self, interaction: discord.Interaction, current: str):
        term = str(current or "").strip().lower()
        subject_type, subject = self._namespace_subject(interaction)
        out: list[app_commands.Choice[str]] = []
        for spec in MODERATION_ACTIONS:
            status = self._action_status_label(interaction.guild, subject_type, subject, spec.key) if interaction.guild else None
            hay = f"{spec.key} {spec.label} {spec.description} {status or ''}".lower()
            if term and term not in hay:
                continue
            suffix = f" • {status}" if status else ""
            out.append(app_commands.Choice(name=self._truncate_choice(f"{spec.label} ({spec.key}){suffix}"), value=spec.key))
        if subject_type and subject is not None:
            out.sort(key=lambda choice: ("schon" not in choice.name and "via" not in choice.name, choice.name.lower()))
        return out[:25]

    @app_commands.command(name="timeout", description="⏳ 𑁉 Timeout setzen")
    @app_commands.describe(user="User", minutes="Minuten (leer = Auto)", reason="Grund")
    async def timeout(self, interaction: discord.Interaction, user: discord.Member, minutes: int | None = None, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "timeout")
        if err:
            return await _ephemeral(interaction, err)

        ok, err, used_minutes, strikes, case_id = await self.service.timeout(interaction.guild, interaction.user, user, minutes, reason)
        if not ok:
            return await _ephemeral(interaction, f"Timeout ging nicht: {err}")

        return await _ephemeral(interaction, f"Timeout gesetzt: **{used_minutes}min** (Strike **{strikes}**). Case: `{case_id}`")

    @app_commands.command(name="warn", description="⚠️ 𑁉 Warnung vergeben")
    @app_commands.describe(user="User", reason="Grund")
    async def warn(self, interaction: discord.Interaction, user: discord.Member, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "warn")
        if err:
            return await _ephemeral(interaction, err)

        strikes, case_id = await self.service.warn(interaction.guild, interaction.user, user, reason)
        return await _ephemeral(interaction, f"Warnung vergeben. Strikes jetzt: **{strikes}**. Case: `{case_id}`")

    @app_commands.command(name="kick", description="👢 𑁉 User kicken")
    @app_commands.describe(user="User", reason="Grund")
    async def kick(self, interaction: discord.Interaction, user: discord.Member, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "kick")
        if err:
            return await _ephemeral(interaction, err)

        ok, err, case_id = await self.service.kick(interaction.guild, interaction.user, user, reason)
        if not ok:
            return await _ephemeral(interaction, f"Kick ging nicht: {err}")
        return await _ephemeral(interaction, f"{user.mention} wurde gekickt. Case: `{case_id}`")

    @app_commands.command(name="ban", description="🔨 𑁉 User bannen")
    @app_commands.describe(user="User", delete_days="Lösche Nachrichten der letzten X Tage (0-7)", reason="Grund")
    async def ban(self, interaction: discord.Interaction, user: discord.User, delete_days: int = 0, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "ban")
        if err:
            return await _ephemeral(interaction, err)

        ok, err, dd, case_id = await self.service.ban(interaction.guild, interaction.user, user, delete_days, reason)
        if not ok:
            return await _ephemeral(interaction, f"Ban ging nicht: {err}")
        return await _ephemeral(interaction, f"<@{user.id}> wurde gebannt. (delete_days={dd}) Case: `{case_id}`")

    @app_commands.command(name="purge", description="🧹 𑁉 Nachrichten löschen")
    @app_commands.describe(amount="Wie viele (1-100)", user="Optional: nur dieser User", reason="Optional: interner Grund")
    async def purge(self, interaction: discord.Interaction, amount: int, user: discord.Member | None = None, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "purge")
        if err:
            return await _ephemeral(interaction, err)

        if not isinstance(interaction.channel, discord.TextChannel):
            return await _ephemeral(interaction, "Nur in normalen Text-Channels.")

        await _defer(interaction)
        deleted, err, case_id = await self.service.purge(interaction.guild, interaction.user, interaction.channel, amount, user)
        if err:
            return await _ephemeral(interaction, f"Purge ging nicht: {err}")
        return await _ephemeral(interaction, f"Gelöscht: **{deleted}** Nachricht(en). Case: `{case_id}`")

    @app_commands.command(name="untimeout", description="✅ 𑁉 Timeout entfernen")
    @app_commands.describe(user="User", reason="Grund")
    async def untimeout(self, interaction: discord.Interaction, user: discord.Member, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "untimeout")
        if err:
            return await _ephemeral(interaction, err)
        try:
            await user.timeout(None, reason=reason or None)
        except Exception as e:
            return await _ephemeral(interaction, f"Timeout entfernen ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"Timeout entfernt für {user.mention}.")

    @app_commands.command(name="mute", description="🔇 𑁉 Mute (Timeout) setzen")
    @app_commands.describe(user="User", minutes="Minuten", reason="Grund")
    async def mute(self, interaction: discord.Interaction, user: discord.Member, minutes: int = 10, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "mute")
        if err:
            return await _ephemeral(interaction, err)
        used = max(1, min(43200, int(minutes)))
        ok, err, used_minutes, strikes, case_id = await self.service.timeout(interaction.guild, interaction.user, user, used, reason)
        if not ok:
            return await _ephemeral(interaction, f"Mute ging nicht: {err}")
        return await _ephemeral(interaction, f"Mute gesetzt: **{used_minutes}min**. Case: `{case_id}`")

    @app_commands.command(name="unban", description="♻️ 𑁉 User entbannen")
    @app_commands.describe(user_id="User-ID", reason="Grund")
    async def unban(self, interaction: discord.Interaction, user_id: int, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "unban")
        if err:
            return await _ephemeral(interaction, err)
        try:
            await interaction.guild.unban(discord.Object(id=int(user_id)), reason=reason or None)
        except Exception as e:
            return await _ephemeral(interaction, f"Unban ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"<@{user_id}> wurde entbannt.")

    @app_commands.command(name="slowmode", description="🐢 𑁉 Slowmode setzen")
    @app_commands.describe(seconds="Sekunden (0-21600)")
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "slowmode")
        if err:
            return await _ephemeral(interaction, err)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await _ephemeral(interaction, "Nur in Text-Channels.")
        s = max(0, min(21600, int(seconds)))
        try:
            await interaction.channel.edit(slowmode_delay=s)
        except Exception as e:
            return await _ephemeral(interaction, f"Slowmode ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"Slowmode gesetzt: **{s}s**.")

    @app_commands.command(name="lock", description="🔒 𑁉 Channel sperren")
    @app_commands.describe(mode="all | send | view")
    @app_commands.choices(mode=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="send", value="send"),
        app_commands.Choice(name="view", value="view"),
    ])
    async def lock(self, interaction: discord.Interaction, mode: app_commands.Choice[str] | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "lock")
        if err:
            return await _ephemeral(interaction, err)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await _ephemeral(interaction, "Nur in Text-Channels.")
        m = self._parse_lock_mode(mode.value if mode else "all")
        ok, err = await self._apply_channel_lock(interaction.guild, interaction.user, interaction.channel, m, True)
        if not ok:
            return await _ephemeral(interaction, f"Lock ging nicht: {err}")
        await _ephemeral(interaction, f"Channel gesperrt. Modus: **{m}**")

    @app_commands.command(name="unlock", description="🔓 𑁉 Channel entsperren")
    @app_commands.describe(mode="all | send | view")
    @app_commands.choices(mode=[
        app_commands.Choice(name="all", value="all"),
        app_commands.Choice(name="send", value="send"),
        app_commands.Choice(name="view", value="view"),
    ])
    async def unlock(self, interaction: discord.Interaction, mode: app_commands.Choice[str] | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "unlock")
        if err:
            return await _ephemeral(interaction, err)
        if not isinstance(interaction.channel, discord.TextChannel):
            return await _ephemeral(interaction, "Nur in Text-Channels.")
        m = self._parse_lock_mode(mode.value if mode else "all")
        ok, err = await self._apply_channel_lock(interaction.guild, interaction.user, interaction.channel, m, False)
        if not ok:
            return await _ephemeral(interaction, f"Unlock ging nicht: {err}")
        await _ephemeral(interaction, f"Channel entsperrt. Modus: **{m}**")

    @app_commands.command(name="nick", description="🪪 𑁉 Nickname setzen")
    @app_commands.describe(user="User", nickname="Neuer Nickname")
    async def nick(self, interaction: discord.Interaction, user: discord.Member, nickname: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "nick")
        if err:
            return await _ephemeral(interaction, err)
        try:
            await user.edit(nick=nickname or None)
        except Exception as e:
            return await _ephemeral(interaction, f"Nick ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"Nickname gesetzt für {user.mention}.")

    @app_commands.command(name="role-add", description="➕ 𑁉 Rolle hinzufügen")
    @app_commands.describe(user="User", role="Rolle")
    async def role_add(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "role_add")
        if err:
            return await _ephemeral(interaction, err)
        try:
            await user.add_roles(role)
        except Exception as e:
            return await _ephemeral(interaction, f"Rolle hinzufügen ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"{role.mention} zu {user.mention} hinzugefügt.")

    @app_commands.command(name="role-remove", description="➖ 𑁉 Rolle entfernen")
    @app_commands.describe(user="User", role="Rolle")
    async def role_remove(self, interaction: discord.Interaction, user: discord.Member, role: discord.Role):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "role_remove")
        if err:
            return await _ephemeral(interaction, err)
        try:
            await user.remove_roles(role)
        except Exception as e:
            return await _ephemeral(interaction, f"Rolle entfernen ging nicht: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"{role.mention} von {user.mention} entfernt.")

    @app_commands.command(name="softban", description="🧼 𑁉 Softban (ban + unban)")
    @app_commands.describe(user="User", delete_days="Lösche Nachrichten der letzten X Tage (0-7)", reason="Grund")
    async def softban(self, interaction: discord.Interaction, user: discord.User, delete_days: int = 1, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "softban")
        if err:
            return await _ephemeral(interaction, err)
        ok, err, case_id = await self.service.softban(interaction.guild, interaction.user, user, delete_days, reason)
        if not ok:
            return await _ephemeral(interaction, f"Softban ging nicht: {err}")
        await _ephemeral(interaction, f"<@{user.id}> softbanned. Case: `{case_id}`")

    @app_commands.command(name="mass-timeout", description="⏳ 𑁉 Timeout für Rolle")
    @app_commands.describe(role="Zielrolle", minutes="Minuten", reason="Grund")
    async def mass_timeout(self, interaction: discord.Interaction, role: discord.Role, minutes: int, reason: str | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "mass_timeout")
        if err:
            return await _ephemeral(interaction, err)
        await _defer(interaction)
        ok_count = 0
        fail_count = 0
        for member in role.members:
            ok, err, used, strikes, case_id = await self.service.timeout(interaction.guild, interaction.user, member, minutes, reason)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
        await _ephemeral(interaction, f"Mass-Timeout fertig. OK: **{ok_count}**, Fehler: **{fail_count}**.")

    @app_commands.command(name="warns", description="📂 𑁉 Warn-History anzeigen")
    @app_commands.describe(user="User", limit="Wie viele (max 20)")
    async def warns(self, interaction: discord.Interaction, user: discord.Member, limit: int = 10):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "warns")
        if err:
            return await _ephemeral(interaction, err)
        n = max(1, min(20, int(limit)))
        rows = await self.bot.db.list_infractions(interaction.guild.id, user.id, limit=n)
        if not rows:
            return await _ephemeral(interaction, "Keine Einträge.")
        lines = []
        for r in rows:
            cid, action, dur, reason, created_at, mod_id = r
            if str(action) not in {"warn", "timeout"}:
                continue
            lines.append(f"• Case `{cid}` • {action} • {reason or '—'}")
        text = "\n".join(lines) if lines else "Keine Warns/Timeouts."
        await _ephemeral(interaction, text)

    @app_commands.command(name="case", description="📁 𑁉 Case anzeigen")
    @app_commands.describe(case_id="Case-ID")
    async def case(self, interaction: discord.Interaction, case_id: int):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "case")
        if err:
            return await _ephemeral(interaction, err)
        row = await self.bot.db.get_infraction(interaction.guild.id, int(case_id))
        if not row:
            return await _ephemeral(interaction, "Case nicht gefunden.")
        cid, action, dur, reason, created_at, mod_id, user_id = row
        text = (
            f"┏`🆔` - Case: `{cid}`\n"
            f"┣`👤` - User: <@{user_id}>\n"
            f"┣`🧑‍⚖️` - Moderator: <@{mod_id}>\n"
            f"┣`⚙️` - Action: **{action}**\n"
            f"┣`⏳` - Dauer: **{dur or 0}**\n"
            f"┗`📝` - Grund: {reason or '—'}"
        )
        await _ephemeral(interaction, text)

    @app_commands.command(name="note", description="📝 𑁉 Mod-Notiz hinzufügen")
    @app_commands.describe(user="User", note="Notiz")
    async def note(self, interaction: discord.Interaction, user: discord.Member, note: str):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "note")
        if err:
            return await _ephemeral(interaction, err)
        case_id = await self.service.add_note(interaction.guild, interaction.user, user, note)
        await _ephemeral(interaction, f"Notiz gespeichert. Case: `{case_id}`")

    @app_commands.command(name="notes", description="🗒️ 𑁉 Mod-Notizen anzeigen")
    @app_commands.describe(user="User", limit="Wie viele (max 20)")
    async def notes(self, interaction: discord.Interaction, user: discord.Member, limit: int = 10):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "notes")
        if err:
            return await _ephemeral(interaction, err)
        n = max(1, min(20, int(limit)))
        rows = await self.bot.db.list_infractions(interaction.guild.id, user.id, limit=n)
        lines = []
        for r in rows:
            cid, action, dur, reason, created_at, mod_id = r
            if str(action) != "note":
                continue
            lines.append(f"• Case `{cid}` • {reason or '—'}")
        text = "\n".join(lines) if lines else "Keine Notizen."
        await _ephemeral(interaction, text)

    @app_commands.command(name="unwarn", description="🧹 𑁉 Letzte Warns/Timeouts entfernen")
    @app_commands.describe(user="User", amount="Anzahl (1-20)")
    async def unwarn(self, interaction: discord.Interaction, user: discord.Member, amount: int = 1):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "unwarn")
        if err:
            return await _ephemeral(interaction, err)
        n = max(1, min(20, int(amount)))
        removed = await self.service.unwarn(interaction.guild, interaction.user, user, n)
        await _ephemeral(interaction, f"Entfernt: **{removed}** Warn/Timeout-Einträge.")

    @app_commands.command(name="case-reason", description="🛠️ 𑁉 Case-Grund ändern")
    @app_commands.describe(case_id="Case-ID", reason="Neuer Grund")
    async def case_reason(self, interaction: discord.Interaction, case_id: int, reason: str):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "case_reason")
        if err:
            return await _ephemeral(interaction, err)
        ok, err = await self.service.update_case_reason(interaction.guild, interaction.user, int(case_id), str(reason))
        if not ok:
            return await _ephemeral(interaction, "Case nicht gefunden oder Update fehlgeschlagen.")
        await _ephemeral(interaction, f"Case `{int(case_id)}` aktualisiert.")

    @app_commands.command(name="clearnotes", description="🧽 𑁉 Mod-Notizen löschen")
    @app_commands.describe(user="User", amount="Anzahl (1-50)")
    async def clear_notes(self, interaction: discord.Interaction, user: discord.Member, amount: int = 10):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "clear_notes")
        if err:
            return await _ephemeral(interaction, err)
        n = max(1, min(50, int(amount)))
        removed = await self.service.clear_notes(interaction.guild, interaction.user, user, n)
        await _ephemeral(interaction, f"Entfernt: **{removed}** Notiz(en).")

    @app_commands.command(name="say", description="📣 𑁉 Nachricht als Bot senden")
    @app_commands.describe(text="Nachricht", channel="Optionaler Zielkanal")
    async def say(self, interaction: discord.Interaction, text: str, channel: discord.TextChannel | None = None):
        if not self._need_guild(interaction):
            return
        err = self._action_error(interaction.user, "say")
        if err:
            return await _ephemeral(interaction, err)
        content = str(text or "").strip()
        if not content:
            return await _ephemeral(interaction, "Text darf nicht leer sein.")
        target = channel if isinstance(channel, discord.TextChannel) else interaction.channel
        if not isinstance(target, discord.TextChannel):
            return await _ephemeral(interaction, "Nur in Text-Channels nutzbar.")
        try:
            await target.send(content)
        except Exception as e:
            return await _ephemeral(interaction, f"Senden fehlgeschlagen: {type(e).__name__}: {e}")
        await _ephemeral(interaction, f"Gesendet in {target.mention}.")

    @commands.command(name="timeout")
    async def p_timeout(self, ctx: commands.Context, user: discord.Member, minutes: int | None = None, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "timeout")
        if err:
            return await self._ctx_reply(ctx, err)
        ok, err, used_minutes, strikes, case_id = await self.service.timeout(ctx.guild, ctx.author, user, minutes, reason)
        if not ok:
            return await self._ctx_reply(ctx, f"Timeout ging nicht: {err}")
        await self._ctx_reply(ctx, f"Timeout gesetzt: **{used_minutes}min** (Strike **{strikes}**). Case: `{case_id}`")

    @commands.command(name="warn")
    async def p_warn(self, ctx: commands.Context, user: discord.Member, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "warn")
        if err:
            return await self._ctx_reply(ctx, err)
        strikes, case_id = await self.service.warn(ctx.guild, ctx.author, user, reason)
        await self._ctx_reply(ctx, f"Warnung vergeben. Strikes jetzt: **{strikes}**. Case: `{case_id}`")

    @commands.command(name="kick")
    async def p_kick(self, ctx: commands.Context, user: discord.Member, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "kick")
        if err:
            return await self._ctx_reply(ctx, err)
        ok, err, case_id = await self.service.kick(ctx.guild, ctx.author, user, reason)
        if not ok:
            return await self._ctx_reply(ctx, f"Kick ging nicht: {err}")
        await self._ctx_reply(ctx, f"{user.mention} wurde gekickt. Case: `{case_id}`")

    @commands.command(name="ban")
    async def p_ban(self, ctx: commands.Context, user: discord.User, delete_days: int = 0, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "ban")
        if err:
            return await self._ctx_reply(ctx, err)
        ok, err, dd, case_id = await self.service.ban(ctx.guild, ctx.author, user, delete_days, reason)
        if not ok:
            return await self._ctx_reply(ctx, f"Ban ging nicht: {err}")
        await self._ctx_reply(ctx, f"<@{user.id}> wurde gebannt. (delete_days={dd}) Case: `{case_id}`")

    @commands.command(name="purge", aliases=["clear", "prune"])
    async def p_purge(self, ctx: commands.Context, amount: int, user: discord.Member | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "purge")
        if err:
            return await self._ctx_reply(ctx, err)
        if not isinstance(ctx.channel, discord.TextChannel):
            return await self._ctx_reply(ctx, "Nur in normalen Text-Channels.")
        deleted, err, case_id = await self.service.purge(ctx.guild, ctx.author, ctx.channel, amount, user)
        if err:
            return await self._ctx_reply(ctx, f"Purge ging nicht: {err}")
        await self._ctx_reply(ctx, f"Gelöscht: **{deleted}** Nachricht(en). Case: `{case_id}`")

    @commands.command(name="untimeout")
    async def p_untimeout(self, ctx: commands.Context, user: discord.Member, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "untimeout")
        if err:
            return await self._ctx_reply(ctx, err)
        try:
            await user.timeout(None, reason=reason or None)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Timeout entfernen ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"Timeout entfernt für {user.mention}.")

    @commands.command(name="mute")
    async def p_mute(self, ctx: commands.Context, user: discord.Member, minutes: int = 10, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "mute")
        if err:
            return await self._ctx_reply(ctx, err)
        used = max(1, min(43200, int(minutes)))
        ok, err, used_minutes, strikes, case_id = await self.service.timeout(ctx.guild, ctx.author, user, used, reason)
        if not ok:
            return await self._ctx_reply(ctx, f"Mute ging nicht: {err}")
        await self._ctx_reply(ctx, f"Mute gesetzt: **{used_minutes}min**. Case: `{case_id}`")

    @commands.command(name="unban")
    async def p_unban(self, ctx: commands.Context, user_id: int, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "unban")
        if err:
            return await self._ctx_reply(ctx, err)
        try:
            await ctx.guild.unban(discord.Object(id=int(user_id)), reason=reason or None)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Unban ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"<@{user_id}> wurde entbannt.")

    @commands.command(name="slowmode")
    async def p_slowmode(self, ctx: commands.Context, seconds: int):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "slowmode")
        if err:
            return await self._ctx_reply(ctx, err)
        if not isinstance(ctx.channel, discord.TextChannel):
            return await self._ctx_reply(ctx, "Nur in Text-Channels.")
        s = max(0, min(21600, int(seconds)))
        try:
            await ctx.channel.edit(slowmode_delay=s)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Slowmode ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"Slowmode gesetzt: **{s}s**.")

    @commands.command(name="lock", aliases=["lockall"])
    async def p_lock(self, ctx: commands.Context, mode: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "lock")
        if err:
            return await self._ctx_reply(ctx, err)
        if not isinstance(ctx.channel, discord.TextChannel):
            return await self._ctx_reply(ctx, "Nur in Text-Channels.")
        m = self._parse_lock_mode(mode or "all")
        ok, err = await self._apply_channel_lock(ctx.guild, ctx.author, ctx.channel, m, True)
        if not ok:
            return await self._ctx_reply(ctx, f"Lock ging nicht: {err}")
        await self._ctx_reply(ctx, f"Channel gesperrt. Modus: **{m}**")

    @commands.command(name="unlock", aliases=["unlockall"])
    async def p_unlock(self, ctx: commands.Context, mode: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "unlock")
        if err:
            return await self._ctx_reply(ctx, err)
        if not isinstance(ctx.channel, discord.TextChannel):
            return await self._ctx_reply(ctx, "Nur in Text-Channels.")
        m = self._parse_lock_mode(mode or "all")
        ok, err = await self._apply_channel_lock(ctx.guild, ctx.author, ctx.channel, m, False)
        if not ok:
            return await self._ctx_reply(ctx, f"Unlock ging nicht: {err}")
        await self._ctx_reply(ctx, f"Channel entsperrt. Modus: **{m}**")

    @commands.command(name="lockw", aliases=["locksend", "lockwrite"])
    async def p_lock_w(self, ctx: commands.Context):
        await self.p_lock(ctx, mode="send")

    @commands.command(name="unlockw", aliases=["unlocksend", "unlockwrite"])
    async def p_unlock_w(self, ctx: commands.Context):
        await self.p_unlock(ctx, mode="send")

    @commands.command(name="locks", aliases=["lockview", "locksee"])
    async def p_lock_s(self, ctx: commands.Context):
        await self.p_lock(ctx, mode="view")

    @commands.command(name="unlocks", aliases=["unlockview", "unlocksee"])
    async def p_unlock_s(self, ctx: commands.Context):
        await self.p_unlock(ctx, mode="view")

    @commands.command(name="nick")
    async def p_nick(self, ctx: commands.Context, user: discord.Member, *, nickname: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "nick")
        if err:
            return await self._ctx_reply(ctx, err)
        try:
            await user.edit(nick=nickname or None)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Nick ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"Nickname gesetzt für {user.mention}.")

    @commands.command(name="roleadd")
    async def p_role_add(self, ctx: commands.Context, user: discord.Member, role: discord.Role):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "role_add")
        if err:
            return await self._ctx_reply(ctx, err)
        try:
            await user.add_roles(role)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Rolle hinzufügen ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"{role.mention} zu {user.mention} hinzugefügt.")

    @commands.command(name="roleremove")
    async def p_role_remove(self, ctx: commands.Context, user: discord.Member, role: discord.Role):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "role_remove")
        if err:
            return await self._ctx_reply(ctx, err)
        try:
            await user.remove_roles(role)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Rolle entfernen ging nicht: {type(e).__name__}: {e}")
        await self._ctx_reply(ctx, f"{role.mention} von {user.mention} entfernt.")

    @commands.command(name="softban")
    async def p_softban(self, ctx: commands.Context, user: discord.User, delete_days: int = 1, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "softban")
        if err:
            return await self._ctx_reply(ctx, err)
        ok, err, case_id = await self.service.softban(ctx.guild, ctx.author, user, delete_days, reason)
        if not ok:
            return await self._ctx_reply(ctx, f"Softban ging nicht: {err}")
        await self._ctx_reply(ctx, f"<@{user.id}> softbanned. Case: `{case_id}`")

    @commands.command(name="masstimeout")
    async def p_mass_timeout(self, ctx: commands.Context, role: discord.Role, minutes: int, *, reason: str | None = None):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "mass_timeout")
        if err:
            return await self._ctx_reply(ctx, err)
        ok_count = 0
        fail_count = 0
        for member in role.members:
            ok, err, used, strikes, case_id = await self.service.timeout(ctx.guild, ctx.author, member, minutes, reason)
            if ok:
                ok_count += 1
            else:
                fail_count += 1
        await self._ctx_reply(ctx, f"Mass-Timeout fertig. OK: **{ok_count}**, Fehler: **{fail_count}**.")

    @commands.command(name="warns")
    async def p_warns(self, ctx: commands.Context, user: discord.Member, limit: int = 10):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "warns")
        if err:
            return await self._ctx_reply(ctx, err)
        n = max(1, min(20, int(limit)))
        rows = await self.bot.db.list_infractions(ctx.guild.id, user.id, limit=n)
        if not rows:
            return await self._ctx_reply(ctx, "Keine Einträge.")
        lines = []
        for r in rows:
            cid, action, dur, reason, created_at, mod_id = r
            if str(action) not in {"warn", "timeout"}:
                continue
            lines.append(f"• Case `{cid}` • {action} • {reason or '—'}")
        await self._ctx_reply(ctx, "\n".join(lines) if lines else "Keine Warns/Timeouts.")

    @commands.command(name="case")
    async def p_case(self, ctx: commands.Context, case_id: int):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "case")
        if err:
            return await self._ctx_reply(ctx, err)
        row = await self.bot.db.get_infraction(ctx.guild.id, int(case_id))
        if not row:
            return await self._ctx_reply(ctx, "Case nicht gefunden.")
        cid, action, dur, reason, created_at, mod_id, user_id = row
        text = (
            f"┏`🆔` - Case: `{cid}`\n"
            f"┣`👤` - User: <@{user_id}>\n"
            f"┣`🧑‍⚖️` - Moderator: <@{mod_id}>\n"
            f"┣`⚙️` - Action: **{action}**\n"
            f"┣`⏳` - Dauer: **{dur or 0}**\n"
            f"┗`📝` - Grund: {reason or '—'}"
        )
        await self._ctx_reply(ctx, text)

    @commands.command(name="note")
    async def p_note(self, ctx: commands.Context, user: discord.Member, *, note: str):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "note")
        if err:
            return await self._ctx_reply(ctx, err)
        case_id = await self.service.add_note(ctx.guild, ctx.author, user, note)
        await self._ctx_reply(ctx, f"Notiz gespeichert. Case: `{case_id}`")

    @commands.command(name="notes")
    async def p_notes(self, ctx: commands.Context, user: discord.Member, limit: int = 10):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "notes")
        if err:
            return await self._ctx_reply(ctx, err)
        n = max(1, min(20, int(limit)))
        rows = await self.bot.db.list_infractions(ctx.guild.id, user.id, limit=n)
        lines = []
        for r in rows:
            cid, action, dur, reason, created_at, mod_id = r
            if str(action) != "note":
                continue
            lines.append(f"• Case `{cid}` • {reason or '—'}")
        await self._ctx_reply(ctx, "\n".join(lines) if lines else "Keine Notizen.")

    @commands.command(name="unwarn")
    async def p_unwarn(self, ctx: commands.Context, user: discord.Member, amount: int = 1):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "unwarn")
        if err:
            return await self._ctx_reply(ctx, err)
        n = max(1, min(20, int(amount)))
        removed = await self.service.unwarn(ctx.guild, ctx.author, user, n)
        await self._ctx_reply(ctx, f"Entfernt: **{removed}** Warn/Timeout-Einträge.")

    @commands.command(name="casereason")
    async def p_case_reason(self, ctx: commands.Context, case_id: int, *, reason: str):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "case_reason")
        if err:
            return await self._ctx_reply(ctx, err)
        ok, err = await self.service.update_case_reason(ctx.guild, ctx.author, int(case_id), str(reason))
        if not ok:
            return await self._ctx_reply(ctx, "Case nicht gefunden oder Update fehlgeschlagen.")
        await self._ctx_reply(ctx, f"Case `{int(case_id)}` aktualisiert.")

    @commands.command(name="clearnotes")
    async def p_clear_notes(self, ctx: commands.Context, user: discord.Member, amount: int = 10):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "clear_notes")
        if err:
            return await self._ctx_reply(ctx, err)
        n = max(1, min(50, int(amount)))
        removed = await self.service.clear_notes(ctx.guild, ctx.author, user, n)
        await self._ctx_reply(ctx, f"Entfernt: **{removed}** Notiz(en).")

    @commands.command(name="say")
    async def p_say(self, ctx: commands.Context, *, text: str):
        if not self._need_ctx(ctx):
            return
        err = self._action_error(ctx.author, "say")
        if err:
            return await self._ctx_reply(ctx, err)
        if not isinstance(ctx.channel, discord.TextChannel):
            return await self._ctx_reply(ctx, "Nur in Text-Channels.")
        raw = str(text or "").strip()
        if not raw:
            return await self._ctx_reply(ctx, "Text darf nicht leer sein.")

        target: discord.TextChannel = ctx.channel
        content = raw
        first, sep, rest = raw.partition(" ")
        parsed_channel: discord.TextChannel | None = None
        if first.startswith("<#") and first.endswith(">"):
            try:
                parsed_channel = ctx.guild.get_channel(int(first[2:-1]))
            except Exception:
                parsed_channel = None
        elif first.isdigit():
            try:
                parsed_channel = ctx.guild.get_channel(int(first))
            except Exception:
                parsed_channel = None
        if isinstance(parsed_channel, discord.TextChannel):
            target = parsed_channel
            content = str(rest if sep else "").strip()

        if not content:
            return await self._ctx_reply(ctx, "Text darf nicht leer sein.")
        try:
            await target.send(content)
        except Exception as e:
            return await self._ctx_reply(ctx, f"Senden fehlgeschlagen: {type(e).__name__}: {e}")
        try:
            await ctx.message.delete()
        except Exception:
            pass
