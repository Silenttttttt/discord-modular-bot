import discord
from discord.ext import commands
from discord import app_commands
from modules.database import get_or_create, update_instance, add_column, SessionLocal
from sqlalchemy import Integer, String, Text
import traceback

async def setup_pokedex_columns():
    await add_column('pokedexentry', 'pokemon_id', Integer, nullable=False, primary_key=True)
    await add_column('pokedexentry', 'name', String, nullable=False)
    await add_column('pokedexentry', 'type', String, nullable=False)
    await add_column('pokedexentry', 'description', Text, nullable=True, final_column=True)

# Import Pokedexentry within the setup function after setting up the columns
async def setup_pokedex_entry():
    await setup_pokedex_columns()
    global Pokedexentry
    from modules.dynamic_models import Pokedexentry


class Pokedex(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_pokemon", description="Add a new Pokémon to the Pokédex")
    @app_commands.describe(pokemon_id="The ID of the Pokémon", name="The name of the Pokémon", type="The type of the Pokémon", description="A description of the Pokémon")
    async def add_pokemon(self, interaction: discord.Interaction, pokemon_id: int, name: str, type: str, description: str = None):
        try:
            pokedex_entry = {
                'pokemon_id': pokemon_id,
                'name': name,
                'type': type,
                'description': description
            }
            await get_or_create(Pokedexentry, **pokedex_entry)
            await interaction.response.send_message(f"Added {name} to the Pokédex!", ephemeral=True)
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            traceback.print_exc()
            await interaction.response.send_message(f"Failed to add Pokémon: {error_message}", ephemeral=True)

    @app_commands.command(name="get_pokemon", description="Get details of a Pokémon from the Pokédex")
    @app_commands.describe(pokemon_id="The ID of the Pokémon")
    async def get_pokemon(self, interaction: discord.Interaction, pokemon_id: int):
        session = SessionLocal()
        try:
            pokemon = session.query(Pokedexentry).filter_by(pokemon_id=pokemon_id).first()
            if pokemon:
                embed = discord.Embed(title=f"Pokémon: {pokemon.name}", description=pokemon.description, color=discord.Color.blue())
                embed.add_field(name="ID", value=pokemon.pokemon_id, inline=True)
                embed.add_field(name="Type", value=pokemon.type, inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(f"Pokémon with ID {pokemon_id} not found in the Pokédex.", ephemeral=True)
        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            traceback.print_exc()
            await interaction.response.send_message(f"Failed to retrieve Pokémon: {error_message}", ephemeral=True)
        finally:
            session.close()

async def setup(bot, restart_fn):
    await setup_pokedex_entry()  # Call setup_pokedex_entry instead of setup_pokedex_columns
    await bot.add_cog(Pokedex(bot))

__intents__ = ["guilds"]
__dependencies__ = ["database"]
__version__ = "1.0.0"
