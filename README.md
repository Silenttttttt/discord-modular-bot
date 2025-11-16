# Discord Modular Bot

A lightweight, modular Discord bot framework written in Python.  
Designed to make it easy to add, remove, and develop features as independent modules (cogs/extensions). Ideal for personal projects, testing ideas, and small-to-medium community bots.

This project also includes a first-class database subsystem — an auto DB migration module and a shared DB layer that makes it simple for individual modules to declare models and share the same connection/session. This was carefully implemented and tested and it works nicely.

---

Table of Contents
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database (auto-migrations & sharing)](#database-auto-migrations--sharing)
- [Running the Bot](#running-the-bot)
- [Creating Modules](#creating-modules)
- [Examples](#examples)
- [Development & Testing](#development--testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

Highlights
- Modular architecture: load/unload modules without touching core logic
- Built-in DB subsystem:
  - Auto DB migration module that runs at startup (configurable)
  - Centralized DB engine/session that modules can import and share
  - Designed so module authors only need to declare models and use the shared session
- Simple configuration via environment variables or .env
- Clear structure for commands, event listeners, and utilities

Requirements
- Python 3.10+ recommended
- discord.py (or a compatible fork)
- SQLAlchemy (or your preferred ORM) — the repo provides an integration layer
- Alembic (used by the migration module) or the included lightweight migration utility
- Optional: python-dotenv if you prefer .env files

Install typical dependencies:
```bash
pip install -r requirements.txt
# If no requirements.txt:
pip install discord.py sqlalchemy alembic python-dotenv
```

Project Structure (example)
- bot.py or main.py — bot bootstrapper and entrypoint
- modules/ — directory containing modular extensions (cogs)
  - modules/example/ — an example module
    - __init__.py
    - cog.py
    - models.py
- db/ — database glue: engine, session, migration runner
  - __init__.py
  - core.py (engine/session creation)
  - migration.py (auto-migration runner)
- config/ or .env — configuration
- README.md — this file

Installation

1. Clone the repository
   ```bash
   git clone https://github.com/Silenttttttt/discord-modular-bot.git
   cd discord-modular-bot
   ```

2. Create and activate a virtual environment (recommended)
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Linux / macOS
   .venv\Scripts\activate      # Windows (PowerShell)
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

Configuration

The bot reads configuration from environment variables. Create a `.env` file in the project root (if you're using python-dotenv) or set these variables in your environment.

Example `.env`:
```env
DISCORD_TOKEN=your-bot-token-here
PREFIX=!
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
AUTO_DB_MIGRATE=true
```

Important:
- DISCORD_TOKEN: Your bot token from the Discord Developer Portal.
- DATABASE_URL: Full SQLAlchemy database URL for the shared DB engine.
- AUTO_DB_MIGRATE: If true, the auto-migration module runs migrations at startup.

Database (auto-migrations & sharing)

This repository includes a DB subsystem designed so modules can add models and automatically participate in migrations and a shared connection/session:

- Auto DB Migration Module
  - On startup, the bot runs a migration step (configurable via AUTO_DB_MIGRATE).
  - The migration system can use Alembic autogenerate or a built-in migration helper to create/upgrade the schema based on declared models.
  - Migrations run once at boot (or can be disabled in production if you prefer manual migrations).

- Shared DB Layer
  - A single engine and session factory is created in the db package (e.g., db/core.py).
  - Modules import the shared session/engine from db to define and operate on models.
  - This avoids multiple engines and provides consistent transactions across modules.

Example - module with models and usage:

modules/example/models.py
```python
from sqlalchemy import Column, Integer, String
from db.core import Base  # Shared declarative base from the project's db layer

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    discord_id = Column(String, unique=True, nullable=False)
    display_name = Column(String)
```

modules/example/cog.py
```python
from discord.ext import commands
from db.core import async_session  # shared async session factory
from modules.example.models import UserProfile

class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setname")
    async def setname(self, ctx, *, name: str):
        async with async_session() as session:
            profile = await session.scalar(
                select(UserProfile).where(UserProfile.discord_id == str(ctx.author.id))
            )
            if profile is None:
                profile = UserProfile(discord_id=str(ctx.author.id), display_name=name)
                session.add(profile)
            else:
                profile.display_name = name
            await session.commit()
            await ctx.send(f"Name set to {name}")
```

How it works at boot:
- bot startup calls db.migration.run_if_enabled() (or similar) which:
  - discovers models (from modules folder or by importing modules)
  - autogenerates and runs migrations (or runs included SQL)
  - ensures the schema is up-to-date before the bot begins handling events
- Modules simply import db.shared objects (Base, engine, session) and declare models or use sessions.

Notes and tips:
- When writing models in modules, import the shared Base (so Alembic / autogenerate sees all models).
- Keep long-running DB work off the event loop (use an async engine or run blocking DB I/O in an executor).

Running the Bot

Start the bot with:
```bash
python bot.py
```
(or `python main.py` depending on your entrypoint)

If AUTO_DB_MIGRATE=true the bot will run DB migration tasks at startup before loading modules. You can disable that if you prefer to run migrations manually with alembic.

Creating Modules

The modular pattern typically uses discord.py cogs or extensions. A recommended layout per module:

modules/<module_name>/
- __init__.py
- cog.py (or <module_name>.py)
- models.py (optional — if the module needs DB tables)

Example `__init__.py` for an extension-based loader:
```python
from .cog import ExampleCog

def setup(bot):
    bot.add_cog(ExampleCog(bot))
```

Dynamic loading (in your bot bootstrapper) can iterate over modules in the `MODULES_FOLDER`, import them, and call `setup(bot)` or use `bot.load_extension('modules.example')`.

Examples

- Ping command
  - Command: `!ping`
  - Response: `Pong!`

- Persistent user settings (DB-backed)
  - Create a module with a `UserSettings` model, store preferences in the shared DB, and read/write via the shared session.

Development & Testing

- Use a dedicated test server for bot development.
- When making changes to modules, you can unload and reload extensions without restarting the whole bot (if your loader supports it):
  ```python
  await bot.unload_extension("modules.example")
  await bot.load_extension("modules.example")
  ```
- Use logging to capture and view errors:
  ```python
  import logging
  logging.basicConfig(level=logging.INFO)
  ```
- For DB testing, use a separate test DATABASE_URL (SQLite in-memory or a CI Postgres instance).

Troubleshooting

- "Bot token invalid": Ensure DISCORD_TOKEN is correct and the bot is not disabled in the Developer Portal.
- Missing intents: If you rely on privileged events (members, presence), enable intents in the Developer Portal and in your code:
  ```python
  intents = discord.Intents.default()
  intents.members = True
  bot = commands.Bot(command_prefix=PREFIX, intents=intents)
  ```
- DB connection errors: Verify DATABASE_URL and that the database is reachable. Check DB credentials and network access.
- Migration issues: If autogenerate doesn't pick up models, ensure modules are imported before migrations run so model classes are registered with the shared Base.

Contributing

Contributions are welcome! Suggested workflow:
1. Fork the repo
2. Create a feature branch
3. Make changes, add tests if applicable
4. Open a pull request with a clear description of your changes

When adding new DB models in a module:
- Use the shared Base from db.core
- Add any initialization code to the module's setup so it's imported during the migration discovery phase
- Provide migration scripts if you need custom SQL beyond autogenerate

License

This repository currently does not contain a license file. If you want others to use and contribute to your project, consider adding an open source license (e.g., MIT, Apache-2.0). Add a LICENSE file in the repo root.

---

If you'd like, I can:
- Commit this README to a new branch and open a pull request for you,
- Add a small example module that demonstrates DB model + command and push it,
- Or tailor the README to match the exact filenames in your repo (bot.py vs main.py, exact db module names).

Tell me which you'd like next and I will proceed.
