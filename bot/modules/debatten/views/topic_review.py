from __future__ import annotations

import re

import discord

from bot.modules.debatten.formatting.debatten_embeds import build_topic_review_embed


async def _send_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(text, ephemeral=True, delete_after=30)
            return
        try:
            await interaction.edit_original_response(content=text, embed=None)
            return
        except Exception:
            pass
        await interaction.followup.send(text, ephemeral=True, delete_after=30)
    except Exception:
        pass


async def _handle_topic_decision(interaction: discord.Interaction, topic_id: int, decision: str):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        await _send_ephemeral(interaction, "Nur im Server nutzbar.")
        return False
    service = getattr(interaction.client, "debatten_service", None)
    if not service:
        await _send_ephemeral(interaction, "Debatten-Service ist nicht verfügbar.")
        return False
    action = "debate_topic_approve" if str(decision) == "approve" else "debate_topic_reject"
    err = service.permission_service.action_error(interaction.user, action)
    if err:
        await _send_ephemeral(interaction, err)
        return False
    await _send_ephemeral(interaction, "Thema wird aktualisiert …")
    status = "approved" if str(decision) == "approve" else "rejected"
    ok, msg = await service.set_topic_status(
        interaction.guild,
        interaction.user,
        topic_id=int(topic_id),
        status=status,
        review_note=None,
        announce=False,
    )
    await _send_ephemeral(interaction, msg)
    if not ok or not interaction.message:
        return ok
    try:
        topic = service._topic_from_row(await service.db.get_debate_topic(int(topic_id)))
        if topic:
            label = "Bestätigt" if status == "approved" else "Abgelehnt"
            embed = build_topic_review_embed(
                service.settings,
                interaction.guild,
                {
                    "topic_id": int(topic["id"]),
                    "title": topic["title"],
                    "description": topic["description"],
                    "status_label": label,
                    "user_id": int(topic["submitted_by"]),
                    "source_label": "Review",
                    "review_note": topic.get("review_note"),
                },
            )
            await interaction.message.edit(embed=embed, view=DebattenTopicReviewView(int(topic_id), disabled=True))
    except Exception:
        pass
    return ok


class DebattenTopicDecisionButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"starry:debate_topic:(?P<topic_id>\d+):(?P<decision>approve|reject)",
):
    def __init__(self, topic_id: int, decision: str, *, disabled: bool = False):
        self.topic_id = int(topic_id)
        self.decision = str(decision)
        label = "Annehmen" if self.decision == "approve" else "Ablehnen"
        style = discord.ButtonStyle.success if self.decision == "approve" else discord.ButtonStyle.danger
        emoji = "✅" if self.decision == "approve" else "⛔"
        button = discord.ui.Button(
            custom_id=f"starry:debate_topic:{self.topic_id}:{self.decision}",
            label=label,
            style=style,
            emoji=emoji,
            disabled=disabled,
        )
        super().__init__(button)

    @classmethod
    def from_custom_id(cls, interaction: discord.Interaction, item: discord.ui.Button, match: re.Match[str]):
        return cls(int(match["topic_id"]), str(match["decision"]))

    async def callback(self, interaction: discord.Interaction):
        await _handle_topic_decision(interaction, self.topic_id, self.decision)


class DebattenTopicReviewView(discord.ui.LayoutView):
    def __init__(self, topic_id: int, *, disabled: bool = False):
        super().__init__(timeout=None)
        row = discord.ui.ActionRow()
        approve = discord.ui.Button(
            custom_id=f"starry:debate_topic:{int(topic_id)}:approve",
            label="Annehmen",
            style=discord.ButtonStyle.success,
            emoji="✅",
            disabled=disabled,
        )
        reject = discord.ui.Button(
            custom_id=f"starry:debate_topic:{int(topic_id)}:reject",
            label="Ablehnen",
            style=discord.ButtonStyle.danger,
            emoji="⛔",
            disabled=disabled,
        )
        approve.callback = self._make_callback(int(topic_id), "approve")
        reject.callback = self._make_callback(int(topic_id), "reject")
        row.add_item(approve)
        row.add_item(reject)
        self.add_item(row)

    def _make_callback(self, topic_id: int, decision: str):
        async def _callback(interaction: discord.Interaction):
            await _handle_topic_decision(interaction, int(topic_id), str(decision))

        return _callback
