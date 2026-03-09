from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.modules.moderation.services.permission_service import PermissionService
from bot.modules.server_guide.services.server_guide_service import ServerGuideService


class ServerGuideCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ServerGuideService(bot, bot.settings, bot.logger)
        self.permission_service = PermissionService(bot.settings, bot.db)

    guide = app_commands.Group(name="guide", description="📘 𑁉 Server-Guide")

    @guide.command(name="build", description="📘 𑁉 Erstellt Guide-Posts im Forum für alle Module")
    @app_commands.describe(channel="Forum-Channel für den Guide")
    async def build(self, interaction: discord.Interaction, channel: discord.ForumChannel | None = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Nur im Server nutzbar.", ephemeral=True)
        err = self.permission_service.action_error(interaction.user, "guide_build")
        if err:
            return await interaction.response.send_message(err, ephemeral=True)

        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.service.build(interaction.guild, channel)
        await interaction.followup.send(msg, ephemeral=True)

    @commands.group(name="guide", invoke_without_command=True)
    async def guide_prefix(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return
        await ctx.reply("Nutze `!guide build` oder `/guide build`.", mention_author=False)

    @guide_prefix.command(name="build")
    async def guide_prefix_build(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return
        err = self.permission_service.action_error(ctx.author, "guide_build")
        if err:
            return await ctx.reply(err, mention_author=False)
        ok, msg = await self.service.build(ctx.guild, None)
        await ctx.reply(msg, mention_author=False)
