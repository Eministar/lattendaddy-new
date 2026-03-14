import discord

from bot.modules.tickets.formatting.ticket_embeds import build_support_panel_container


class SupportPanelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ticket starten",
            style=discord.ButtonStyle.primary,
            custom_id="support_panel_start",
            emoji="🎫",
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user:
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        try:
            await interaction.user.send(
                "🧩 𑁉 SUPPORT START\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "Schreib mir jetzt kurz dein Anliegen.\n"
                "Danach schicke ich dir erst eine Bestätigung.\n"
                "Erst nach deinem Klick öffne ich das Ticket."
            )
            await interaction.response.send_message("Ich habe dir eine DM geschickt.", ephemeral=True)
        except Exception:
            await interaction.response.send_message("DM nicht möglich. Bitte DMs aktivieren.", ephemeral=True)


class SupportPanelView(discord.ui.LayoutView):
    def __init__(self, settings=None, guild: discord.Guild | None = None, stats: dict | None = None):
        super().__init__(timeout=None)
        total = int((stats or {}).get("total", 0) or 0)
        open_ = int((stats or {}).get("open_", 0) or 0)
        active = int((stats or {}).get("active", 0) or 0)
        container = build_support_panel_container(settings, guild, total, open_, active, SupportPanelButton())
        self.add_item(container)
