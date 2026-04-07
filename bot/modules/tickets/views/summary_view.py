import discord


class TeamNoteModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="📝 Team-Notiz")
        self.service = service
        self.note = discord.ui.TextInput(
            label="Notiz",
            required=True,
            max_length=1500,
            style=discord.TextStyle.paragraph,
            placeholder="Interne Notiz fürs Team.",
        )
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        text = (self.note.value or "").strip()
        await self.service.post_team_note(interaction, text)


class StatusModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="🏷️ Status setzen")
        self.service = service
        self.status = discord.ui.TextInput(
            label="Status",
            required=True,
            max_length=32,
            style=discord.TextStyle.short,
            placeholder="z.B. 🟢 OFFEN",
        )
        self.add_item(self.status)

    async def on_submit(self, interaction: discord.Interaction):
        text = (self.status.value or "").strip()
        await self.service.set_status_label(interaction, text)


class EscalationModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="⚠️ Ticket eskalieren")
        self.service = service
        self.level = discord.ui.TextInput(
            label="Eskalations-Level (1-5)",
            required=True,
            max_length=1,
            style=discord.TextStyle.short,
            placeholder="1",
        )
        self.reason = discord.ui.TextInput(
            label="Grund (optional)",
            required=False,
            max_length=500,
            style=discord.TextStyle.paragraph,
            placeholder="Kurzer Grund für die Eskalation.",
        )
        self.add_item(self.level)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        level = (self.level.value or "").strip()
        try:
            level_int = int(level)
        except Exception:
            return await interaction.response.send_message("Level muss 1-5 sein.", ephemeral=True)
        await self.service.escalate_ticket(interaction, level_int, (self.reason.value or "").strip())


class PrioritySelect(discord.ui.Select):
    def __init__(self, service):
        self.service = service
        options = [
            discord.SelectOption(label="Niedrig", value="1", emoji="🟢"),
            discord.SelectOption(label="Normal", value="2", emoji="🟡"),
            discord.SelectOption(label="Hoch", value="3", emoji="🟠"),
            discord.SelectOption(label="Dringend", value="4", emoji="🔴"),
        ]
        super().__init__(
            placeholder="Priorität ändern…",
            options=options,
            custom_id="starry:ticket_priority",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            value = int(self.values[0])
        except Exception:
            return await interaction.response.send_message("Ungültige Priorität.", ephemeral=True)
        await self.service.set_priority(interaction, value)


class StatusSelect(discord.ui.Select):
    def __init__(self, service):
        self.service = service
        labels = service.settings.get("ticket.status_labels", None) or [
            "🟢 OFFEN",
            "⏳ WARTET AUF ANTWORT",
            "🛠️ IN BEARBEITUNG",
            "⏸️ WARTEND",
            "🚨 ESKALATION",
        ]
        options = []
        seen = set()
        for label in labels:
            text = str(label).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            options.append(discord.SelectOption(label=text, value=text))
        options.append(discord.SelectOption(label="Custom…", value="__custom__", emoji="✍️"))
        super().__init__(
            placeholder="Status setzen…",
            options=options[:25],
            custom_id="starry:ticket_status",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        if value == "__custom__":
            return await interaction.response.send_modal(StatusModal(self.service))
        await self.service.set_status_label(interaction, value)


class CategorySelect(discord.ui.Select):
    def __init__(self, service):
        self.service = service
        categories = service.settings.get("categories", {}) or {}
        options = []
        for key, cfg in categories.items():
            label = str((cfg or {}).get("label", key)).strip() or str(key)
            options.append(discord.SelectOption(label=label[:100], value=str(key), emoji="🧭"))
        if not options:
            options = [discord.SelectOption(label="Keine Kategorien", value="__none__")]
        super().__init__(
            placeholder="Kategorie wechseln…",
            options=options[:25],
            custom_id="starry:ticket_category",
            min_values=1,
            max_values=1,
        )
        if options and options[0].value == "__none__":
            self.disabled = True
            self.fixed_disabled = True
        else:
            self.fixed_disabled = False

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]
        if value == "__none__":
            return await interaction.response.send_message("Keine Kategorien konfiguriert.", ephemeral=True)
        await self.service.change_category(interaction, value)


class ParticipantSelect(discord.ui.UserSelect):
    def __init__(self, service):
        self.service = service
        super().__init__(
            placeholder="Teilnehmer hinzufügen…",
            min_values=1,
            max_values=1,
            custom_id="starry:ticket_add",
        )

    async def callback(self, interaction: discord.Interaction):
        user = self.values[0] if self.values else None
        if not user:
            return await interaction.response.send_message("Kein User ausgewählt.", ephemeral=True)
        await self.service.add_participant(interaction, user)


class SummaryView(discord.ui.LayoutView):
    ACTION_BY_CUSTOM_ID = {
        "starry:ticket_claim": "ticket_claim",
        "starry:ticket_add": "ticket_add",
        "starry:ticket_note": "ticket_note",
        "starry:ticket_close": "ticket_close",
        "starry:ticket_reopen": "ticket_reopen",
        "starry:ticket_transcript": "ticket_transcript",
        "starry:ticket_escalate": "ticket_escalate",
        "starry:ticket_priority": "ticket_priority",
        "starry:ticket_status": "ticket_status",
        "starry:ticket_category": "ticket_category",
    }

    def __init__(
        self,
        service,
        ticket_id: int,
        claimed: bool = False,
        status: str = "open",
        container: discord.ui.Container | None = None,
    ):
        super().__init__(timeout=None)
        self.service = service
        self.ticket_id = int(ticket_id)
        self.claimed = bool(claimed)
        self.status = str(status or "open")

        if container:
            self.add_item(container)

        self.btn_claim = discord.ui.Button(
            custom_id="starry:ticket_claim",
            style=discord.ButtonStyle.success,
            label="Ticket beanspruchen",
            emoji="✅",
        )
        self.btn_claim.callback = self._on_claim

        self.btn_note = discord.ui.Button(
            custom_id="starry:ticket_note",
            style=discord.ButtonStyle.primary,
            label="Team-Notiz",
            emoji="📝",
        )
        self.btn_note.callback = self._on_note

        self.btn_close = discord.ui.Button(
            custom_id="starry:ticket_close",
            style=discord.ButtonStyle.danger,
            label="Ticket schließen",
            emoji="🔒",
        )
        self.btn_close.callback = self._on_close

        self.btn_reopen = discord.ui.Button(
            custom_id="starry:ticket_reopen",
            style=discord.ButtonStyle.secondary,
            label="Ticket wieder öffnen",
            emoji="🔓",
        )
        self.btn_reopen.callback = self._on_reopen

        self.btn_transcript = discord.ui.Button(
            custom_id="starry:ticket_transcript",
            style=discord.ButtonStyle.secondary,
            label="Transcript",
            emoji="🧾",
        )
        self.btn_transcript.callback = self._on_transcript

        self.btn_escalate = discord.ui.Button(
            custom_id="starry:ticket_escalate",
            style=discord.ButtonStyle.secondary,
            label="Eskalieren",
            emoji="⚠️",
        )
        self.btn_escalate.callback = self._on_escalate

        self.select_priority = PrioritySelect(self.service)
        self.select_status = StatusSelect(self.service)
        self.select_category = CategorySelect(self.service)
        self.select_participant = ParticipantSelect(self.service)

        row_main = discord.ui.ActionRow()
        row_main.add_item(self.btn_claim)
        row_main.add_item(self.btn_note)
        row_main.add_item(self.btn_close)
        row_main.add_item(self.btn_reopen)
        row_main.add_item(self.btn_transcript)

        row_escalate = discord.ui.ActionRow()
        row_escalate.add_item(self.btn_escalate)

        row_participant = discord.ui.ActionRow()
        row_participant.add_item(self.select_participant)

        row_priority = discord.ui.ActionRow()
        row_priority.add_item(self.select_priority)

        row_status = discord.ui.ActionRow()
        row_status.add_item(self.select_status)

        row_category = discord.ui.ActionRow()
        row_category.add_item(self.select_category)

        self.add_item(row_main)
        self.add_item(row_escalate)
        self.add_item(row_participant)
        self.add_item(row_priority)
        self.add_item(row_status)
        self.add_item(row_category)

        self._apply_claim_state()

    def _apply_claim_state(self):
        is_closed = str(self.status) == "closed"
        if self.claimed:
            self.btn_claim.label = "Ticket freigeben"
            self.btn_claim.style = discord.ButtonStyle.secondary
            self.btn_claim.emoji = "🔓"
        else:
            self.btn_claim.label = "Ticket beanspruchen"
            self.btn_claim.style = discord.ButtonStyle.success
            self.btn_claim.emoji = "✅"

        self.btn_reopen.disabled = not is_closed
        self.btn_close.disabled = is_closed
        self.btn_claim.disabled = is_closed
        self.btn_note.disabled = is_closed
        self.btn_escalate.disabled = is_closed
        self.select_participant.disabled = is_closed
        self.select_priority.disabled = is_closed
        self.select_status.disabled = is_closed
        self.select_category.disabled = is_closed or getattr(self.select_category, "fixed_disabled", False)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            try:
                await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("Nur im Server nutzbar.", ephemeral=True)
            return False

        data = getattr(interaction, "data", {}) or {}
        custom_id = str(data.get("custom_id") or "")
        action = self.ACTION_BY_CUSTOM_ID.get(custom_id)
        err = self.service.permission_service.action_error(interaction.user, action) if action else None
        if err:
            try:
                await interaction.response.send_message(err, ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send(err, ephemeral=True)
            return False

        return True

    async def _on_claim(self, interaction: discord.Interaction):
        await self.service.toggle_claim(interaction)

    async def _on_note(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TeamNoteModal(self.service))

    async def _on_close(self, interaction: discord.Interaction):
        await self.service.close_ticket(interaction, "")

    async def _on_reopen(self, interaction: discord.Interaction):
        await self.service.reopen_ticket(interaction)

    async def _on_transcript(self, interaction: discord.Interaction):
        await self.service.send_transcript(interaction, None)

    async def _on_escalate(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EscalationModal(self.service))
