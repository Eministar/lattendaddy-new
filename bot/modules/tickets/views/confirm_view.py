import discord

from bot.modules.tickets.formatting.ticket_embeds import build_dm_ticket_confirmation_container


class TicketConfirmView(discord.ui.LayoutView):
    def __init__(
        self,
        service,
        guild: discord.Guild | None = None,
        category_label: str = "Support",
        preview_text: str | None = None,
        attachment_count: int = 0,
        state: str = "pending",
        ticket_id: int | None = None,
        include_container: bool = True,
    ):
        super().__init__(timeout=None)
        self.service = service
        self.guild = guild
        self.state = str(state or "pending").lower()

        if include_container:
            container = build_dm_ticket_confirmation_container(
                self.service.settings,
                guild,
                category_label,
                preview_text,
                attachment_count=attachment_count,
                state=self.state,
                ticket_id=ticket_id,
            )
            self.add_item(container)

        self.btn_confirm = discord.ui.Button(
            label="Ticket eröffnen",
            style=discord.ButtonStyle.success,
            custom_id="starry:ticket_confirm_open",
            emoji="✅",
        )
        self.btn_confirm.callback = self._on_confirm

        self.btn_cancel = discord.ui.Button(
            label="Verwerfen",
            style=discord.ButtonStyle.secondary,
            custom_id="starry:ticket_confirm_cancel",
            emoji="✖️",
        )
        self.btn_cancel.callback = self._on_cancel

        disabled = self.state != "pending"
        self.btn_confirm.disabled = disabled
        self.btn_cancel.disabled = disabled

        row = discord.ui.ActionRow()
        row.add_item(self.btn_confirm)
        row.add_item(self.btn_cancel)
        self.add_item(row)

    async def _on_confirm(self, interaction: discord.Interaction):
        await self.service.confirm_pending_ticket(interaction)

    async def _on_cancel(self, interaction: discord.Interaction):
        await self.service.cancel_pending_ticket(interaction)
