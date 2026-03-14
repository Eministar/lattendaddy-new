from __future__ import annotations

from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.moderation.services.permission_service import PermissionService
from bot.modules.setup.services.setup_service import SettingMeta, SetupService


async def _respond(
    interaction: discord.Interaction,
    *,
    text: str | None = None,
    embed: discord.Embed | None = None,
    file: discord.File | None = None,
):
    kwargs = {"ephemeral": True}
    if text is not None:
        kwargs["content"] = text
    if embed is not None:
        kwargs["embed"] = embed
    if file is not None:
        kwargs["file"] = file
    if not interaction.response.is_done():
        await interaction.response.send_message(**kwargs)
        return
    await interaction.followup.send(**kwargs)


class SetupCommands(commands.Cog):
    setup = app_commands.Group(name="setup", description="⚙️ Module und Einstellungen konfigurieren")

    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "setup_service", None) or SetupService(bot.settings, bot.db)
        self.permission_service = PermissionService(bot.settings, bot.db)

    @staticmethod
    def _truncate(text: str, limit: int = 100) -> str:
        raw = str(text or "").strip()
        if len(raw) <= limit:
            return raw
        return raw[: limit - 1].rstrip() + "…"

    @staticmethod
    def _in_guild(interaction: discord.Interaction) -> bool:
        return bool(interaction.guild and isinstance(interaction.user, discord.Member))

    def _permission_error(self, interaction: discord.Interaction, action: str) -> str | None:
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not interaction.guild or member is None:
            return "Nur im Server nutzbar."
        return self.permission_service.action_error(member, action)

    def _resolve_module_key(self, raw: str | None) -> str | None:
        return self.service.resolve_module_key(raw)

    def _resolve_meta(self, interaction: discord.Interaction, module_raw: str | None, setting_raw: str | None) -> tuple[str | None, SettingMeta | None]:
        module_key = self._resolve_module_key(module_raw)
        if not module_key or not interaction.guild:
            return module_key, None
        meta = self.service.resolve_setting_meta(module_key, setting_raw, guild_id=interaction.guild.id)
        return module_key, meta

    def _module_embed(self, module_key: str, guild_id: int) -> discord.Embed:
        info = self.service._module_info(module_key)
        metas = self.service.setting_metas(module_key, guild_id=guild_id)
        override_count = sum(1 for meta in metas if self.service.has_override(guild_id, meta.full_path))
        lines: list[str] = []
        if override_count:
            for meta in metas:
                if not self.service.has_override(guild_id, meta.full_path):
                    continue
                preview = self.service.format_value(self.service.current_value(guild_id, meta), meta, limit=70)
                lines.append(f"`{meta.relative_path}` → `{preview}`")
                if len(lines) >= 8:
                    break
        else:
            for meta in metas[:8]:
                preview = self.service.format_value(self.service.current_value(guild_id, meta), meta, limit=70)
                lines.append(f"`{meta.relative_path}` → `{preview}`")
        embed = discord.Embed(
            title=f"{info['emoji']} {info['label']}",
            description=(
                f"Modul-Key: `{module_key}`\n"
                f"Settings: `{len(metas)}`\n"
                f"Guild-Overrides: `{override_count}`"
            ),
            color=discord.Color.blurple(),
        )
        if lines:
            embed.add_field(
                name="Überblick",
                value="\n".join(lines),
                inline=False,
            )
        embed.set_footer(text="Voller Dump ist als Textdatei angehängt.")
        return embed

    def _setting_embed(self, guild_id: int, meta: SettingMeta, headline: str | None = None) -> discord.Embed:
        source = "Guild-Override" if self.service.has_override(guild_id, meta.full_path) else "Global / Basis"
        current_value = self.service.format_value(self.service.current_value(guild_id, meta), meta, limit=900)
        global_value = self.service.format_value(self.service.global_value(meta), meta, limit=900)
        embed = discord.Embed(
            title=headline or f"⚙️ {meta.module_key} • {meta.relative_path}",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Pfad", value=f"`{meta.full_path}`", inline=False)
        embed.add_field(name="Typ", value=meta.type_label, inline=True)
        embed.add_field(name="Quelle", value=source, inline=True)
        example = self.service.example_value(meta)
        if example:
            embed.add_field(name="Beispiel", value=f"`{self._truncate(example, 120)}`", inline=True)
        embed.add_field(name="Aktuell", value=f"`{current_value}`", inline=False)
        embed.add_field(name="Global", value=f"`{global_value}`", inline=False)
        return embed

    def _module_dump_file(self, guild_id: int, module_key: str) -> discord.File:
        payload = self.service.module_text(guild_id, module_key).encode("utf-8")
        return discord.File(BytesIO(payload), filename=f"setup-{module_key}-{guild_id}.txt")

    async def _module_choices(self, current: str) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=self._truncate(label), value=value)
            for label, value in self.service.module_choices(current)
        ]

    async def _setting_choices(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        module_key = self._resolve_module_key(getattr(interaction.namespace, "module", None))
        if not module_key:
            return []
        return [
            app_commands.Choice(name=self._truncate(label), value=value)
            for label, value in self.service.setting_choices(interaction.guild.id, module_key, current)
        ]

    async def _value_choices(self, interaction: discord.Interaction, current: str, *, mode: str) -> list[app_commands.Choice[str]]:
        if not interaction.guild:
            return []
        module_key, meta = self._resolve_meta(
            interaction,
            getattr(interaction.namespace, "module", None),
            getattr(interaction.namespace, "setting", None),
        )
        if not module_key or meta is None:
            return []
        return [
            app_commands.Choice(name=self._truncate(label), value=value)
            for label, value in self.service.value_choices(interaction, meta, current, mode=mode)
        ]

    @setup.command(name="modules", description="🧩 Verfügbare Setup-Module anzeigen")
    async def modules(self, interaction: discord.Interaction):
        err = self._permission_error(interaction, "setup_view")
        if err:
            return await _respond(interaction, text=err)
        lines = []
        for module_key in self.service.module_keys():
            info = self.service._module_info(module_key)
            alias_text = ", ".join(info["aliases"][:3]) if info["aliases"] else "keine"
            lines.append(f"{info['emoji']} `{module_key}` • {info['label']} • Alias: {alias_text}")
        embed = discord.Embed(
            title="⚙️ Setup-Module",
            description="\n".join(lines[:25]),
            color=discord.Color.blurple(),
        )
        if len(lines) > 25:
            embed.add_field(name="Hinweis", value=f"Noch `{len(lines) - 25}` weitere Module sind per Autocomplete sichtbar.", inline=False)
        await _respond(interaction, embed=embed)

    @setup.command(name="show", description="👀 Aktuelles Modul oder Setting anzeigen")
    @app_commands.describe(module="Modul-Key oder Alias", setting="Optional ein bestimmtes Setting")
    async def show(self, interaction: discord.Interaction, module: str, setting: str | None = None):
        err = self._permission_error(interaction, "setup_view")
        if err:
            return await _respond(interaction, text=err)
        if not interaction.guild:
            return await _respond(interaction, text="Nur im Server nutzbar.")
        module_key = self._resolve_module_key(module)
        if not module_key:
            return await _respond(interaction, text="Unbekanntes Modul. Nutze die Autocomplete bei `/setup show`.")
        if setting is None:
            await _respond(
                interaction,
                embed=self._module_embed(module_key, interaction.guild.id),
                file=self._module_dump_file(interaction.guild.id, module_key),
            )
            return
        meta = self.service.resolve_setting_meta(module_key, setting, guild_id=interaction.guild.id)
        if meta is None:
            return await _respond(interaction, text="Unbekanntes Setting für dieses Modul.")
        await _respond(interaction, embed=self._setting_embed(interaction.guild.id, meta))

    @setup.command(name="set", description="✍️ Ein Setting gezielt setzen")
    @app_commands.describe(module="Modul-Key oder Alias", setting="Setting-Pfad", value="Neuer Wert")
    async def set_value(self, interaction: discord.Interaction, module: str, setting: str, value: str):
        err = self._permission_error(interaction, "setup_manage")
        if err:
            return await _respond(interaction, text=err)
        if not self._in_guild(interaction):
            return await _respond(interaction, text="Nur im Server nutzbar.")
        module_key, meta = self._resolve_meta(interaction, module, setting)
        if not module_key:
            return await _respond(interaction, text="Unbekanntes Modul. Nutze die Autocomplete.")
        if meta is None:
            return await _respond(interaction, text="Unbekanntes Setting für dieses Modul.")
        try:
            _, message = await self.service.set_value(interaction.guild.id, meta, value)
        except ValueError as exc:
            return await _respond(interaction, text=str(exc))
        embed = self._setting_embed(interaction.guild.id, meta, headline="⚙️ Setting aktualisiert")
        embed.description = message
        await _respond(interaction, embed=embed)

    @setup.command(name="add", description="➕ Einzelwerte zu einer Liste hinzufügen")
    @app_commands.describe(module="Modul-Key oder Alias", setting="Listen-Setting", value="Wert oder CSV-Liste")
    async def add_value(self, interaction: discord.Interaction, module: str, setting: str, value: str):
        err = self._permission_error(interaction, "setup_manage")
        if err:
            return await _respond(interaction, text=err)
        if not self._in_guild(interaction):
            return await _respond(interaction, text="Nur im Server nutzbar.")
        module_key, meta = self._resolve_meta(interaction, module, setting)
        if not module_key:
            return await _respond(interaction, text="Unbekanntes Modul. Nutze die Autocomplete.")
        if meta is None:
            return await _respond(interaction, text="Unbekanntes Setting für dieses Modul.")
        try:
            _, message = await self.service.add_list_values(interaction.guild.id, meta, value)
        except ValueError as exc:
            return await _respond(interaction, text=str(exc))
        embed = self._setting_embed(interaction.guild.id, meta, headline="⚙️ Liste erweitert")
        embed.description = message
        await _respond(interaction, embed=embed)

    @setup.command(name="remove", description="➖ Einzelwerte aus einer Liste entfernen")
    @app_commands.describe(module="Modul-Key oder Alias", setting="Listen-Setting", value="Wert oder CSV-Liste")
    async def remove_value(self, interaction: discord.Interaction, module: str, setting: str, value: str):
        err = self._permission_error(interaction, "setup_manage")
        if err:
            return await _respond(interaction, text=err)
        if not self._in_guild(interaction):
            return await _respond(interaction, text="Nur im Server nutzbar.")
        module_key, meta = self._resolve_meta(interaction, module, setting)
        if not module_key:
            return await _respond(interaction, text="Unbekanntes Modul. Nutze die Autocomplete.")
        if meta is None:
            return await _respond(interaction, text="Unbekanntes Setting für dieses Modul.")
        try:
            _, message = await self.service.remove_list_values(interaction.guild.id, meta, value)
        except ValueError as exc:
            return await _respond(interaction, text=str(exc))
        embed = self._setting_embed(interaction.guild.id, meta, headline="⚙️ Liste reduziert")
        embed.description = message
        await _respond(interaction, embed=embed)

    @setup.command(name="reset", description="♻️ Ein Setting auf den globalen Wert zurücksetzen")
    @app_commands.describe(module="Modul-Key oder Alias", setting="Setting-Pfad")
    async def reset_value(self, interaction: discord.Interaction, module: str, setting: str):
        err = self._permission_error(interaction, "setup_manage")
        if err:
            return await _respond(interaction, text=err)
        if not self._in_guild(interaction):
            return await _respond(interaction, text="Nur im Server nutzbar.")
        module_key, meta = self._resolve_meta(interaction, module, setting)
        if not module_key:
            return await _respond(interaction, text="Unbekanntes Modul. Nutze die Autocomplete.")
        if meta is None:
            return await _respond(interaction, text="Unbekanntes Setting für dieses Modul.")
        changed, message = await self.service.reset_value(interaction.guild.id, meta)
        embed = self._setting_embed(interaction.guild.id, meta, headline="⚙️ Setting zurückgesetzt" if changed else "⚙️ Kein Override vorhanden")
        embed.description = message
        await _respond(interaction, embed=embed)

    @show.autocomplete("module")
    @set_value.autocomplete("module")
    @add_value.autocomplete("module")
    @remove_value.autocomplete("module")
    @reset_value.autocomplete("module")
    async def module_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._module_choices(current)

    @show.autocomplete("setting")
    @set_value.autocomplete("setting")
    @add_value.autocomplete("setting")
    @remove_value.autocomplete("setting")
    @reset_value.autocomplete("setting")
    async def setting_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._setting_choices(interaction, current)

    @set_value.autocomplete("value")
    async def set_value_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._value_choices(interaction, current, mode="set")

    @add_value.autocomplete("value")
    async def add_value_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._value_choices(interaction, current, mode="add")

    @remove_value.autocomplete("value")
    async def remove_value_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self._value_choices(interaction, current, mode="remove")
