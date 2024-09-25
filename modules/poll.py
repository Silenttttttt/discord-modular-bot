import discord
from discord.ext import commands
from discord import app_commands

class Poll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createpoll", description="Create a poll")
    @app_commands.describe(question="The poll question")
    async def create_poll(self, interaction: discord.Interaction, question: str):
        poll_message = await interaction.response.send_message(f"Poll created: {question}\nReact with 👍 or 👎", ephemeral=False)
        poll_message = await interaction.original_response()
        await poll_message.add_reaction('👍')
        await poll_message.add_reaction('👎')

    @app_commands.command(name="endpoll", description="End a poll")
    @app_commands.describe(message_id="The ID of the poll message")
    async def end_poll(self, interaction: discord.Interaction, message_id: int):
        poll_message = await interaction.channel.fetch_message(message_id)
        if not poll_message:
            await interaction.response.send_message("Poll message not found!", ephemeral=True)
            return

        thumbs_up = discord.utils.get(poll_message.reactions, emoji='👍')
        thumbs_down = discord.utils.get(poll_message.reactions, emoji='👎')

        await interaction.response.send_message(f"Poll results:\n👍: {thumbs_up.count - 1}\n👎: {thumbs_down.count - 1}", ephemeral=False)

async def setup(bot):
    await bot.add_cog(Poll(bot))
