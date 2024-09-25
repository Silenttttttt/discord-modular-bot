# main.py

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import traceback
import sys
import asyncio

# Default configuration
default_config = {
    "bot_token": "",
    "modules": [
        "database",
        "game",
        "poll",
        "ultra_mod",
        "invite_tracker"
    ]
}

has_run = False
config_path = 'config.json'



# try:
#     os.remove('modules/dynamic_models.py')
#     print("Successfully deleted modules/dynamic_models.py")
# except FileNotFoundError:
#     print("modules/dynamic_models.py does not exist")
# except Exception as e:
#     print(f"An error occurred while trying to delete modules/dynamic_models.py: {e}")
#     traceback.print_exc()


def load_config():
    if not os.path.exists(config_path):
        with open(config_path, 'w') as file:
            json.dump(default_config, file, indent=4)
            print(f'Created default configuration file at {config_path}')

    with open(config_path, 'r') as file:
        config = json.load(file)

    if not config['bot_token']:
        config['bot_token'] = input("Enter your Discord bot token: ")
        with open(config_path, 'w') as file:
            json.dump(config, file, indent=4)
    return config

def aggregate_intents(modules):
    intents = discord.Intents.default()
    for module in modules:
        try:
            mod = __import__(f"modules.{module}", fromlist=["*"])
            module_intents = getattr(mod, "__intents__", [])
            for intent in module_intents:
                if not getattr(intents, intent, False):
                    setattr(intents, intent, True)
        except ImportError as e:
            print(f"Failed to import module {module}: {e}")
        except AttributeError as e:
            print(f"Module {module} does not define required intents: {e}")
    return intents

config = load_config()
bot_token = config['bot_token']
initial_extensions = config['modules']

intents = aggregate_intents(initial_extensions)
bot = commands.Bot(command_prefix="!", intents=intents)

async def load_extension(extension, loaded_extensions):
    if extension in loaded_extensions:
        print(f"Skipping already loaded extension: {extension}")
        return

    try:
        # Import the module
        module = __import__(f"modules.{extension}", fromlist=["*"])
        
        # Check for dependencies
        dependencies = getattr(module, "__dependencies__", [])
        missing_dependencies = [dep for dep in dependencies if dep not in initial_extensions]

        if missing_dependencies:
            print(f"Warning: Module '{extension}' has missing dependencies: {', '.join(missing_dependencies)}")
            return

        unsatisfied_dependencies = [dep for dep in dependencies if dep not in loaded_extensions]

        if unsatisfied_dependencies:
            print(f"Warning: Module '{extension}' loaded before its dependencies: {', '.join(unsatisfied_dependencies)}")
            return

        # Call the setup function with required arguments
        await module.setup(bot, restart_program)

        loaded_extensions.add(extension)
        print(f"Loaded extension {extension}")
    except Exception as e:
        print(f"Failed to load extension {extension}: {e}")
        traceback.print_exc()

async def load_extensions():
    loaded_extensions = set()

    for extension in initial_extensions:
        await load_extension(extension, loaded_extensions)


async def unload_extensions():
    for extension in initial_extensions:
        try:
            await bot.unload_extension(f'modules.{extension}')
            print(f"Unloaded extension {extension}")
        except Exception as e:
            print(f"Failed to unload extension {extension}: {e}")
            traceback.print_exc()

async def restart_program():
    """Restart the current program."""
    try:
        print("Restarting program...")
        await asyncio.sleep(2)  # Slight delay to prevent infinite loop
        os.execl(sys.executable, sys.executable, *sys.argv)
    except Exception as e:
        print(f"Failed to restart program: {e}")
        traceback.print_exc()

@bot.event
async def on_ready():
    global has_run
    if not has_run:
        await load_extensions()
        await bot.tree.sync()
        print(f'Logged in as {bot.user}')
        has_run = True

@bot.tree.command(name="reload", description="Reload program")
@commands.is_owner()
async def reload(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(f"Reloading...", ephemeral=True)
        await restart_program()
    except Exception as e:
        await interaction.response.send_message(f"Failed to reload: {e}", ephemeral=True)
        traceback.print_exc()

if __name__ == "__main__":
    bot.run(bot_token)
