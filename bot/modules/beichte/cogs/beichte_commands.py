from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.beichte.services.beichte_service import BeichteService
from bot.modules.moderation.services.permission_service import PermissionService


class BeichteCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = getattr(bot, "beichte_service", None) or BeichteService(bot, bot.settings, bot.db, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    beichte = app_commands.Group(name="beichte", description="🕊️ 𑁉 Beichte")

    async def _resolve_thread(
        self,
        interaction: discord.Interaction,
        thread: discord.Thread | None,
    ) -> tuple[discord.Thread | None, str | None]:
        if not interaction.guild:
            return None, "Nur im Server nutzbar."

        target = thread
        if not target and isinstance(interaction.channel, discord.Thread):
            target = interaction.channel

        if not target or not isinstance(target, discord.Thread):
            return None, "Bitte einen Thread angeben oder den Befehl im Thread nutzen."

        forum = await self.service._get_forum_channel(interaction.guild)
        if not forum:
            return None, "Forum-Channel ist nicht konfiguriert."

        parent = getattr(target, "parent", None)
        if not parent or int(parent.id) != int(forum.id):
            return None, "Das ist kein Beichte-Thread."

        return target, None

    def _fmt_iso(self, value: str | None) -> str:
        if not value:
            return "—"
        try:
            dt = datetime.fromisoformat(str(value))
        except Exception:
            return str(value)
        try:
            return discord.utils.format_dt(dt)
        except Exception:
            return str(value)

    @beichte.command(name="setup", description="⚙️ 𑁉 Beichte konfigurieren")
    @app_commands.describe(forum="Forum-Channel für Beichte")
    async def setup(self, interaction: discord.Interaction, forum: discord.ForumChannel):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_setup")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.configure(interaction.guild, forum)
        await interaction.response.send_message("Konfiguration gespeichert.", ephemeral=True)

    @beichte.command(name="panel", description="📌 𑁉 Info im Forum senden")
    @app_commands.describe(forum="Optional: Forum-Channel überschreiben")
    async def panel(self, interaction: discord.Interaction, forum: discord.ForumChannel | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_panel")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)
        await self.service.send_panel(interaction, forum)

    @beichte.command(name="close", description="🔒 𑁉 Beichte-Thread schließen")
    @app_commands.describe(thread="Optional: Thread auswählen")
    async def close(self, interaction: discord.Interaction, thread: discord.Thread | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_close")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        target, error = await self._resolve_thread(interaction, thread)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        try:
            await target.edit(locked=True, archived=True)
        except Exception:
            return await interaction.response.send_message("Thread konnte nicht geschlossen werden.", ephemeral=True)
        await interaction.response.send_message("Thread geschlossen.", ephemeral=True)

    @beichte.command(name="open", description="🔓 𑁉 Beichte-Thread öffnen")
    @app_commands.describe(thread="Optional: Thread auswählen")
    async def open(self, interaction: discord.Interaction, thread: discord.Thread | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_open")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        target, error = await self._resolve_thread(interaction, thread)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        try:
            await target.edit(locked=False, archived=False)
        except Exception:
            return await interaction.response.send_message("Thread konnte nicht geöffnet werden.", ephemeral=True)
        await interaction.response.send_message("Thread geöffnet.", ephemeral=True)

    @beichte.command(name="delete", description="🗑️ 𑁉 Beichte-Thread löschen")
    @app_commands.describe(thread="Optional: Thread auswählen")
    async def delete(self, interaction: discord.Interaction, thread: discord.Thread | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_delete")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        target, error = await self._resolve_thread(interaction, thread)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        await interaction.response.send_message("Thread wird gelöscht…", ephemeral=True)
        try:
            await target.delete()
        except Exception:
            pass

    @beichte.command(name="who", description="🧾 𑁉 Ersteller eines Beichte-Threads anzeigen")
    @app_commands.describe(thread="Optional: Thread auswählen")
    async def who(self, interaction: discord.Interaction, thread: discord.Thread | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "beichte_who")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        target, error = await self._resolve_thread(interaction, thread)
        if error:
            return await interaction.response.send_message(error, ephemeral=True)

        row = await self.service.db.get_beichte_thread(int(interaction.guild.id), int(target.id))
        if not row:
            return await interaction.response.send_message("Kein Eintrag in der Datenbank gefunden.", ephemeral=True)

        _, _, user_id, anonymous, created_at = row
        author = f"<@{int(user_id)}>"
        created = self._fmt_iso(str(created_at))
        text = (
            f"**Ersteller:** {author}\n"
            f"**Anonym:** {'Ja' if int(anonymous) else 'Nein'}\n"
            f"**Erstellt:** {created}"
        )
        await interaction.response.send_message(text, ephemeral=True)
