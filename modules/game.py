import discord
from discord.ext import commands
from discord import app_commands
import random

class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="startgame", description="Start a guessing game")
    async def start_game(self, interaction: discord.Interaction):
        await interaction.response.send_message("Game started! Guess a number between 1 and 10.")

    @app_commands.command(name="guess", description="Guess a number between 1 and 10")
    @app_commands.describe(number="The number you guess")
    async def guess(self, interaction: discord.Interaction, number: int):
        answer = random.randint(1, 10)
        if number == answer:
            await interaction.response.send_message(f"Congratulations {interaction.user.mention}, you guessed the right number!")
        else:
            await interaction.response.send_message(f"Sorry {interaction.user.mention}, the correct number was {answer}.")

async def setup(bot):
    await bot.add_cog(Game(bot))
