from __future__ import annotations

import discord

from bot.modules.debatten.formatting.debatten_embeds import build_notice_embed, build_panel_container


async def _send_ephemeral(
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
        else:
            await interaction.followup.send(content=text, embed=embed, ephemeral=True, delete_after=30)
    except Exception:
        pass


class DebateTopicSubmitModal(discord.ui.Modal):
    def __init__(self, service):
        super().__init__(title="Debattenthema einreichen")
        self.service = service
        self.title_input = discord.ui.TextInput(
            label="Thema",
            style=discord.TextStyle.short,
            required=True,
            max_length=120,
            placeholder="Bitte nur politische Themen, z. B. Sollte die Schuldenbremse reformiert werden?",
        )
        self.description_input = discord.ui.TextInput(
            label="Beschreibung",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000,
            placeholder="Beschreibe kurz, worüber debattiert werden soll. Reiche bitte nur politische Debattenthemen ein.",
        )
        self.add_item(self.title_input)
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction):
        await self.service.submit_topic(
            interaction,
            title=str(self.title_input.value),
            description=str(self.description_input.value),
        )


class DebattenSignupButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Für nächste Debatte anmelden",
            emoji="🗳️",
            style=discord.ButtonStyle.primary,
            custom_id="starry:debatten:signup",
        )

    async def callback(self, interaction: discord.Interaction):
        service = getattr(interaction.client, "debatten_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Debatten-Service ist nicht verfügbar.")
        await service.toggle_signup(interaction)


class DebattenTopicButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Politisches Thema senden",
            emoji="🧠",
            style=discord.ButtonStyle.secondary,
            custom_id="starry:debatten:topic_submit",
        )

    async def callback(self, interaction: discord.Interaction):
        service = getattr(interaction.client, "debatten_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Debatten-Service ist nicht verfügbar.")
        await interaction.response.send_modal(DebateTopicSubmitModal(service))


class DebattenArchiveSelect(discord.ui.Select):
    def __init__(self, archive_options: list[discord.SelectOption] | None = None, disabled: bool = False):
        options = archive_options or [
            discord.SelectOption(
                label="Noch kein Archiv vorhanden",
                value="0",
                description="Abgeschlossene Debatten erscheinen hier.",
            )
        ]
        super().__init__(
            placeholder="Archiv öffnen …",
            custom_id="starry:debatten:archive",
            options=options[:25],
            min_values=1,
            max_values=1,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction):
        service = getattr(interaction.client, "debatten_service", None)
        if not service:
            return await _send_ephemeral(interaction, "Debatten-Service ist nicht verfügbar.")
        try:
            event_id = int(str(self.values[0]))
        except Exception:
            event_id = 0
        if event_id <= 0:
            return await _send_ephemeral(interaction, "Noch keine archivierte Debatte vorhanden.")
        embed = await service.archive_embed(interaction.guild, event_id)
        return await _send_ephemeral(interaction, embed=embed)


class DebattenPanelView(discord.ui.LayoutView):
    def __init__(
        self,
        settings=None,
        guild: discord.Guild | None = None,
        state: dict | None = None,
        archive_options: list[discord.SelectOption] | None = None,
        archive_disabled: bool = False,
    ):
        super().__init__(timeout=None)
        signup_button = DebattenSignupButton()
        topic_button = DebattenTopicButton()
        archive_select = DebattenArchiveSelect(archive_options=archive_options, disabled=archive_disabled)
        container = build_panel_container(
            settings,
            guild,
            state or {},
            signup_button,
            topic_button,
            archive_select,
        )
        self.add_item(container)
