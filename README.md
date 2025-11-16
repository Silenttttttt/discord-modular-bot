# Discord Modular Bot

A lightweight, modular Discord bot framework written in Python.  
Designed to make it easy to add, remove, and develop features as independent modules (cogs/extensions). Ideal for personal projects, testing ideas, and small-to-medium community bots.

This project also includes a first-class, built-in database subsystem — a custom auto-migration module and a shared DB layer that makes it simple for individual modules to declare models, add tables/columns at runtime, and share the same connection/session. This subsystem is implemented in modules/database.py and has been tested and works nicely.

---

Table of Contents
- [Highlights](#highlights)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database (custom auto-migrations & sharing)](#database-custom-auto-migrations--sharing)
- [Running the Bot](#running-the-bot)
- [Creating Modules](#creating-modules)
- [Examples](#examples)
- [Development & Testing](#development--testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

Highlights
- Modular architecture: load/unload modules without touching core logic.
- Built-in DB subsystem (custom, no external migration tool):
  - Runtime dynamic model generator (modules/dynamic_models.py) that the DB module maintains.
  - Helpers to create pending tables and add columns at runtime (ALTER TABLE).
  - Centralized SQLAlchemy engine/session and convenience helpers (get_or_create, update_instance, add_column, etc.).
  - Modules can rely on the shared Base/Session objects and the DB module to keep the schema in sync.
- Simple configuration via environment variables or .env.
- Clear structure for commands, event listeners, and utilities.

Requirements
- Python 3.10+ recommended
- discord.py (or a compatible fork)
- SQLAlchemy (this repo uses SQLAlchemy ORM)
- Optional: python-dotenv if you prefer .env files

Install typical dependencies:
```bash
pip install -r requirements.txt
# If no requirements.txt:
pip install discord.py sqlalchemy python-dotenv
```

Project Structure (example)
- bot.py or main.py — bot bootstrapper and entrypoint
- modules/ — directory containing modular extensions (cogs)
  - modules/database.py — custom DB subsystem (dynamic models, runtime migrations)
  - modules/dynamic_models.py — generated file containing model classes (auto-generated)
  - modules/example/ — an example module
    - __init__.py
    - cog.py
    - models.py (optional; see notes)
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
DATABASE_URL=sqlite:///database.db
AUTO_DB_MIGRATE=true
```

Important:
- DISCORD_TOKEN: Your bot token from the Discord Developer Portal.
- DATABASE_URL: SQLAlchemy URL for the shared DB engine (default: sqlite:///database.db).
- AUTO_DB_MIGRATE: If true, the DB module will run its init/setup steps at startup.

Database (custom auto-migrations & sharing)

This repository uses a custom DB subsystem implemented in modules/database.py. Key points:

- No external migration tooling. The project uses its own dynamic model generation and runtime schema modification logic.
- Dynamic models:
  - modules/database.py generates modules/dynamic_models.py based on a set of built-in default tables and existing DB metadata.
  - dynamic_models.py exports model classes (e.g., User, Server, ServerUser) and is re-generated/updated when tables or columns change.
- Runtime schema changes:
  - add_column(...) will run an ALTER TABLE to add a column if needed.
  - create_pending_tables() and create_table(...) create new tables when requested.
  - The DB module keeps track of added columns and updates the dynamic models file accordingly.
- Shared objects and helpers:
  - engine (SQLAlchemy engine), SessionLocal (scoped session factory), Base (declarative base wrapper), and convenience functions like get_or_create(), update_instance(), init_db(), and setup(bot, restart_fn) are provided.
  - init_db() will generate or load dynamic models and create any missing tables (calls Base.metadata.create_all).
  - setup(bot, restart_fn) is an async initializer the bot calls at module startup to wire the bot instance into the DB module and ensure pending tables/columns are created.

How modules should interact with the DB subsystem
- Prefer using helper functions (get_or_create, update_instance, SessionLocal) from modules/database.py rather than re-creating engines.
- If you need model classes, import them from modules.dynamic_models after setup/init has run:
  - from modules.dynamic_models import User, Server, ServerUser
- If a module requires new tables/columns at runtime, use the DB helper functions (e.g., add_column or a setup-time registration that creates pending tables) so the DB module can create the schema and update dynamic_models.py.

Example - quick usage pattern (conceptual)
```python
# in a cog
from modules.database import SessionLocal, get_or_create
from modules.dynamic_models import User

async def ensure_profile(user_id):
    user = await get_or_create(User, discord_id=str(user_id))
    return user
```

Running the Bot

Start the bot with:
```bash
python bot.py
```
(or `python main.py` depending on your entrypoint)

If AUTO_DB_MIGRATE=true the bot will run the DB module's init/setup logic at startup (generating dynamic models, creating pending tables, and applying runtime column additions) before loading other modules.

Creating Modules

The modular pattern typically uses discord.py cogs or extensions. A recommended layout per module:

modules/<module_name>/
- __init__.py
- cog.py (or <module_name>.py)
- models.py (optional — if you want to provide model definitions, coordinate with the DB module's generation logic)

Example `__init__.py` for an extension-based loader:
```python
from .cog import ExampleCog

def setup(bot):
    bot.add_cog(ExampleCog(bot))
```

Examples

- Ping command
  - Command: `!ping`
  - Response: `Pong!`

- Persistent user settings (DB-backed)
  - Use modules.dynamic_models (or DB helpers) to store and retrieve per-user settings.

Development & Testing

- Use a dedicated test server for bot development.
- When making changes to modules, you can unload and reload extensions without restarting the whole bot (if your loader supports it).
- For DB testing, use a separate DATABASE_URL (SQLite in-memory or test Postgres).
- Pay attention to dynamic_models.py: it's generated by the DB module — if you change model generation logic, re-run init_db.

Troubleshooting

- "Bot token invalid": Ensure DISCORD_TOKEN is correct and the bot is not disabled in the Developer Portal.
- Missing intents: If you rely on privileged events (members, presence), enable intents in the Developer Portal and in your code.
- DB connection errors: Verify DATABASE_URL and that the database is reachable.
- If dynamic_models.py is malformed: delete modules/dynamic_models.py and restart with AUTO_DB_MIGRATE enabled so the DB module regenerates it.
- If autogenerate-like behavior doesn't find your model: ensure the module that defines fields or calls add_column is imported/ran before init_db/creation is attempted (or use the DB module APIs to register pending tables).

Contributing

Contributions are welcome! Suggested workflow:
1. Fork the repo
2. Create a feature branch
3. Make changes, add tests if applicable
4. Open a pull request with a clear description of your changes

When adding new DB models or schema changes:
- Prefer using the DB module's APIs so the dynamic model generator and runtime migration helpers can update modules/dynamic_models.py consistently.
- Add documentation in the module explaining any required DB migrations or special initialization steps.
