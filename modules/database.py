# modules/database.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, MetaData, Table, text, BigInteger, Text, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session, relationship, registry, Session
from sqlalchemy.orm.state import InstanceState
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.exc import OperationalError

from datetime import datetime
import logging
import traceback
import asyncio
import os
import importlib

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

mapper_registry = registry()
metadata = mapper_registry.metadata

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

model_column_defaults = {}
pending_tables = {}
added_columns = {}
default_functions = {}


restart_program_fn = None
bot_instance = None

class MyBase:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()

    def get_context(self):
        return Session.object_session(self)._instantiate_session(None, None)

Base = declarative_base(cls=MyBase)


type_imports = {
    'Integer': 'from sqlalchemy import Integer',
    'String': 'from sqlalchemy import String',
    'DateTime': 'from sqlalchemy import DateTime',
    'BigInteger': 'from sqlalchemy import BigInteger',
    'Text': 'from sqlalchemy import Text',
    'ForeignKey': 'from sqlalchemy import ForeignKey',
    'Boolean': 'from sqlalchemy import Boolean',
    'Float': 'from sqlalchemy import Float',
    'Numeric': 'from sqlalchemy import Numeric',
    'SmallInteger': 'from sqlalchemy import SmallInteger',
    'Binary': 'from sqlalchemy import Binary',
    'Unicode': 'from sqlalchemy import Unicode',
    'UnicodeText': 'from sqlalchemy import UnicodeText',
    'LargeBinary': 'from sqlalchemy import LargeBinary',
    'Interval': 'from sqlalchemy import Interval',
    'PickleType': 'from sqlalchemy import PickleType',
    'Enum': 'from sqlalchemy import Enum',
}


def format_default_value(default):
    if default == datetime.utcnow:
        return "default=datetime.utcnow"
    if callable(default):
        return f"default={default.__name__}"
    return f"default='{default}'" if isinstance(default, str) else f"default={default}"



def generate_dynamic_models():
    imports = {"from sqlalchemy import Column", "from datetime import datetime"}
    class_definitions = []
    file_path = os.path.join(os.path.dirname(__file__), 'dynamic_models.py')

    # Ensure the default models are always present
    default_tables = {
        'User': [
            ('discord_id', String, None, False, True),
            ('global_join_date', DateTime, datetime.utcnow, False, False),
            ('username', String, None, False, False),
            ('avatar', Text, None, True, False),
            ('account_creation_date', DateTime, datetime.utcnow, False, False)
        ],
        'Server': [
            ('guild_id', BigInteger, None, False, True),
            ('guild_name', Text, None, False, False),
            ('guild_owner_id', BigInteger, None, False, False),
            ('guild_icon_url', Text, None, True, False),
            ('language', String, 'en', True, False)
        ],
        'ServerUser': [
            ('id', String, None, False, True),  # Add id as the primary key
            ('user_id', String, None, False, False),
            ('server_id', BigInteger, None, False, False),
            ('join_date', DateTime, datetime.utcnow, False, False)
        ]
    }

    for table_name, columns in default_tables.items():
        class_definitions.append(f"\nclass {table_name}(Base):\n")
        class_definitions.append(f"    __tablename__ = '{table_name.lower()}'\n")
        class_definitions.append(f"    __table_args__ = {{'extend_existing': True}}\n")
        for column_name, column_type, default, nullable, primary_key in columns:
            default_value = format_default_value(default)

            nullable = "nullable=False" if not nullable else "nullable=True"
            pk = "primary_key=True" if primary_key else ""
            imports.add(type_imports.get(column_type.__name__, f'from sqlalchemy import {column_type.__name__}'))
            class_definitions.append(f"    {column_name} = Column({column_type.__name__}, {default_value}, {nullable}, {pk})\n")

    for table_name, table in metadata.tables.items():
        class_definitions.append(f"\nclass {table_name.capitalize()}(Base):\n")
        class_definitions.append(f"    __tablename__ = '{table_name}'\n")
        class_definitions.append(f"    __table_args__ = {{'extend_existing': True}}\n")
        for column in table.columns:
            column_type = column.type.__class__.__name__
            default = format_default_value(column.default.arg) if column.default is not None else "default=None"
            nullable = "nullable=False" if not column.nullable else "nullable=True"
            primary_key = "primary_key=True" if column.primary_key else ""
            imports.add(type_imports.get(column_type, f'from sqlalchemy import {column_type}'))
            class_definitions.append(f"    {column.name} = Column({column_type}, {default}, {nullable}, {primary_key})\n")

    with open(file_path, 'w') as file:
        file.write("from sqlalchemy.orm import relationship\n")
        file.write("from .database import Base\n\n")
        for imp in sorted(imports):
            file.write(f"{imp}\n")
        for definition in class_definitions:
            file.write(definition)

    # Load default functions after generating the models
    load_default_functions()





def update_dynamic_models_file(class_name, column_name=None, column_type=None, default=None, nullable=True, primary_key=False):
    file_path = os.path.join(os.path.dirname(__file__), 'dynamic_models.py')
    imports = set()
    base_import = "from .database import Base"
    relationship_import = "from sqlalchemy.orm import relationship"
    imports.update([base_import, relationship_import])

    with open(file_path, 'r') as file:
        lines = file.readlines()

    new_lines = []
    in_class_definition = False
    class_found = False
    column_inserted = False
    column_exists = False
    class_content_lines = []

    for line in lines:
        stripped_line = line.strip()

        # Collect imports without duplicates
        if stripped_line.startswith('from sqlalchemy') or stripped_line.startswith('from datetime'):
            imports.add(stripped_line)
            continue

        if stripped_line == base_import or stripped_line == relationship_import:
            continue

        # Mark the start of the class definition
        if stripped_line.startswith(f'class {class_name}'):
            print(f"Class {class_name} found.")
            class_found = True
            in_class_definition = True

        # Collect lines within the class definition
        if in_class_definition:
            class_content_lines.append(line)
            # Check if the line defines the column
            if stripped_line.startswith(f"{column_name} = Column("):
                print(f"Column {column_name} already exists in class {class_name}.")
                column_exists = True

            if not line.startswith('    ') and not stripped_line.startswith(f'class {class_name}'):
                in_class_definition = False
                if not column_exists and not column_inserted:
                    print(f"Inserting column {column_name} in class {class_name}.")
                    class_content_lines.insert(-1, f"    {column_name} = Column({column_type.__name__}, {format_default_value(default)}, {'nullable=False' if not nullable else 'nullable=True'}, {'primary_key=True' if primary_key else ''})\n")
                    column_inserted = True
            continue

        if stripped_line:  # Skip empty lines
            new_lines.append(line)

    # Ensure the class content is reassembled properly
    if class_content_lines:
        if not column_exists and not column_inserted:
            print(f"Inserting column {column_name} in class {class_name} at the end of class content.")
            class_content_lines.insert(-1, f"    {column_name} = Column({column_type.__name__}, {format_default_value(default)}, {'nullable=False' if not nullable else 'nullable=True'}, {'primary_key=True' if primary_key else ''})\n")
        new_lines.extend(class_content_lines)

    # If the class was not found, add it to the end
    if not class_found:
        print(f"Class {class_name} not found. Adding it to the end.")
        new_lines.append(f"\nclass {class_name}(Base):\n")
        new_lines.append(f"    __tablename__ = '{class_name.lower()}'\n")
        new_lines.append(f"    {column_name} = Column({column_type.__name__}, {format_default_value(default)}, {'nullable=False' if not nullable else 'nullable=True'}, {'primary_key=True' if primary_key else ''})\n")

    imports.add(type_imports.get(column_type.__name__, f'from sqlalchemy import {column_type.__name__}'))

    with open(file_path, 'w') as file:
        file.write(f"{relationship_import}\n")
        file.write(f"{base_import}\n")
        for imp in sorted(imports):
            if imp not in {relationship_import, base_import}:
                file.write(f"{imp}\n")
        file.write("\n")  # add a blank line between imports and class definitions
        for line in new_lines:
            if not line.startswith('from .database import Base') and not line.startswith('from sqlalchemy.orm import relationship'):
                file.write(line)



# Function to add columns to the database table
async def add_column(table_name, column_name, column_type, default=None, nullable=True, final_column=False, primary_key=False):
    if column_type is None:
        raise ValueError("column_type must be provided")

    print(f"Adding column: {column_name}, Type: {column_type}, Default: {default}, Nullable: {nullable}, Primary Key: {primary_key}")

    new_column_added = False
    try:
        metadata.reflect(bind=engine)
        table_name_lower = table_name.lower()
        table = metadata.tables.get(table_name_lower)

        if table is None:
            print("Table does not exist, creating table.")
            # Create the table if it does not exist
            pending_tables[table_name_lower] = [{
                'name': column_name,
                'type': column_type,
                'default': default,
                'nullable': nullable,
                'primary_key': primary_key
            }]
            print(f"Pending tables after adding column: {pending_tables}")
            await create_table(table_name_lower)
            table = metadata.tables.get(table_name_lower)
        else:
            if column_name in table.c:
                print("Column already exists in the table.")
                track_added_column(table_name_lower, column_name, column_type, default, nullable, primary_key)
                if callable(default):
                    default_functions[f"{table_name_lower}.{column_name}"] = default
                return True

            if default is not None:
                if isinstance(default, str):
                    default_clause = f" DEFAULT '{default}'"
                else:
                    default_clause = f" DEFAULT {default}"
            else:
                default_clause = ""

            null_clause = " NOT NULL" if not nullable else ""
            primary_key_clause = " PRIMARY KEY" if primary_key else ""

            with engine.connect() as conn:
                print(f"Executing SQL to add column: ALTER TABLE {table_name_lower} ADD COLUMN {column_name} {column_type.__visit_name__.upper()}{default_clause}{null_clause}{primary_key_clause}")
                conn.execute(text(f'ALTER TABLE {table_name_lower} ADD COLUMN {column_name} {column_type.__visit_name__.upper()}{default_clause}{null_clause}{primary_key_clause}'))
            metadata.reflect(bind=engine)
            register_model_defaults(table_name_lower, column_name, default)
            track_added_column(table_name_lower, column_name, column_type, default, nullable, primary_key)
            new_column_added = True

            if callable(default):
                default_functions[f"{table_name_lower}.{column_name}"] = default

            if final_column and new_column_added:
                print("Final column added, updating dynamic models and restarting program.")
                if update_dynamic_models_from_added_columns():
                    await asyncio.sleep(1)
                    await restart_program_fn()
            return True
    except OperationalError as e:
        if "duplicate column name" in str(e):
            print("Duplicate column name error.")
            track_added_column(table_name_lower, column_name, column_type, default, nullable, primary_key)
            if callable(default):
                default_functions[f"{table_name_lower}.{column_name}"] = default
        else:
            print("OperationalError occurred.")
            traceback.print_exc()
        return False


# modules/database.py

def clear_base_classes():
    global Base
    # Clear existing classes from Base metadata to avoid conflicts
    Base.metadata.clear()
    mapper_registry.dispose()  # Dispose of the mapper registry to clear any cached mappings
    # Redefine the Base class to ensure it's completely reset
    Base = declarative_base(cls=MyBase)

    
def get_model_class_by_table_name(table_name):
    file_path = os.path.join(os.path.dirname(__file__), 'dynamic_models.py')
    if not os.path.exists(file_path):
        return None
    
    class_name = None
    table_name_lower = table_name.lower()
    with open(file_path, 'r') as file:
        lines = file.readlines()
        for i, line in enumerate(lines):
            if f"__tablename__ = '{table_name_lower}'" in line.lower():
                if i > 0 and lines[i-1].strip().startswith("class "):
                    class_name = lines[i-1].strip().split(' ')[1].split('(')[0]
                    break
    
    if class_name:
        from modules import dynamic_models
        clear_base_classes()  # Clear existing classes from Base metadata
        importlib.reload(dynamic_models)
#        print(dynamic_models.__dict__)
        return getattr(dynamic_models, class_name, None)
    
    
    return None

async def create_pending_tables():
    for table_name in list(pending_tables.keys()):
        await create_table(table_name)

async def create_table(table_name):
    try:
        columns = pending_tables.pop(table_name, [])
        if columns:
            # Validate that all columns have a valid column_type
            for column in columns:
                col_name = column['name']
                col_type = column['type']
                col_default = column['default']
                col_nullable = column['nullable']
                col_primary_key = column.get('primary_key', False)
                
                if col_type is None:
                    raise ValueError(f"column_type must be provided for column '{col_name}'")

            table = Table(table_name, metadata, *[
                Column(column['name'], column['type'], 
                       primary_key=column.get('primary_key', False), 
                       autoincrement=column['name'] == 'id', 
                       nullable=column['nullable'])
                for column in columns
            ])
            table.create(bind=engine)
            metadata.reflect(bind=engine)

            # Fetch the actual class name
            class_name = get_model_class_by_table_name(table_name)

            # Update the dynamic models file with the correct class name
            if class_name:
                update_dynamic_models_file(class_name.__name__)
            else:
                # If class_name is None, it means the table is new, so we need to add it to dynamic_models.py
                for column in columns:
                    update_dynamic_models_file(
                        table_name.capitalize(),
                        column_name=column['name'],
                        column_type=column['type'],
                        default=column['default'],
                        nullable=column['nullable'],
                        primary_key=column.get('primary_key', False)
                    )

            return True
        else:
            print(f"No columns defined for table {table_name}.")
            return False
    except Exception as e:
        print(f"Failed to create table {table_name}: {e}")
        traceback.print_exc()
        return False

async def fetch_discord_user_info(discord_id):
    user = await bot_instance.fetch_user(discord_id)
    return {
        'username': user.name,
        'avatar': str(user.avatar),
        'account_creation_date': user.created_at.replace(tzinfo=None)
    }

async def fetch_discord_server_info(guild_id):
    guild = bot_instance.get_guild(guild_id)
    if guild is None:
        guild = await bot_instance.fetch_guild(guild_id)
    return {
        'guild_name': guild.name,
        'guild_owner_id': guild.owner_id,
        'guild_icon_url': str(guild.icon_url) if guild.icon else None
    }

async def fetch_discord_server_user_info(user_id, guild_id):
    guild = bot_instance.get_guild(guild_id)
    if guild is None:
        guild = await bot_instance.fetch_guild(guild_id)
    member = await guild.fetch_member(user_id)
    return {
        'join_date': member.joined_at.replace(tzinfo=None)
    }


def generate_serveruser_id(context):
    if context:
        params = context.get_current_parameters()
        return f"{params['user_id']}_{params['server_id']}"
    return None

def load_default_functions():
    # Add functions to the default_functions dictionary
    default_functions['serveruser.id'] = generate_serveruser_id


def check_and_generate_dynamic_models():
    file_path = os.path.join(os.path.dirname(__file__), 'dynamic_models.py')
    if not os.path.exists(file_path):
        generate_dynamic_models()
        load_default_functions()
    else:
        try:
            #import modules.dynamic_models
            load_default_functions()  # Load default functions even if dynamic_models.py already exists
        except (ImportError, SyntaxError):
            generate_dynamic_models()
            load_default_functions()




def make_naive_datetime(dt):
    if isinstance(dt, datetime):
        if dt.tzinfo is not None:
            dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return dt
    elif callable(dt):
        dt = dt()
        if isinstance(dt, datetime):
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
    elif hasattr(dt, 'arg') and callable(dt.arg):
        dt = dt.arg(None)
        if isinstance(dt, datetime):
            if dt.tzinfo is not None:
                dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
            return dt
    return dt


def generate_serveruser_id(instance):
    return f"{instance.user_id}_{instance.server_id}"



async def get_or_create(model, **kwargs):
    session = SessionLocal()
    try:
        instance = session.query(model).filter_by(**kwargs).first()
        if not instance:
            model_name = model.__tablename__
            instance_data = kwargs

            if model_name == 'user':
                discord_user_info = await fetch_discord_user_info(instance_data['discord_id'])
                instance_data.update(discord_user_info)

            if model_name == 'server':
                discord_server_info = await fetch_discord_server_info(instance_data['guild_id'])
                instance_data.update(discord_server_info)

            if model_name == 'serveruser':
                server_id = instance_data['server_id']
                user_id = instance_data['user_id']
                server_user_instance = session.query(model).filter_by(server_id=server_id, user_id=user_id).first()
                if server_user_instance:
                    return server_user_instance

                server = session.query(get_model_class_by_table_name('server')).filter_by(guild_id=server_id).first()
                if not server:
                    discord_server_info = await fetch_discord_server_info(server_id)
                    server_data = {
                        'guild_id': server_id,
                        **discord_server_info
                    }
                    Server = get_model_class_by_table_name('server')
                    server = Server(**server_data)
                    session.add(server)
                    session.commit()
                    session.refresh(server)

                discord_server_user_info = await fetch_discord_server_user_info(user_id, server_id)
                instance_data.update(discord_server_user_info)

            # Generate default values for the instance
            temp_instance = model(**instance_data)
            for key, default_func in default_functions.items():
                table, col = key.split('.')
                if table == model_name and (col not in instance_data or instance_data[col] is None):
                    setattr(temp_instance, col, default_func(temp_instance))

            session.add(temp_instance)
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                # Fetch the existing instance in case of an integrity error
                instance = session.query(model).filter_by(**kwargs).first()
                if not instance:
                    raise e
            else:
                session.refresh(temp_instance)
                instance = temp_instance

        return instance
    except Exception as e:
        print(f"Failed to get or create {model.__name__}: {e}")
        traceback.print_exc()
    finally:
        session.close()








async def update_instance(model, filter_by, **kwargs):
    session = SessionLocal()
    try:
        instance = session.query(model).filter_by(**filter_by).first()
        if instance:
            for key, value in kwargs.items():
                print(f"Setting {key} to {value} (type: {type(value)}) for {model.__name__}")
                setattr(instance, key, value)
            
            session.commit()
            session.refresh(instance)
        return instance
    except Exception as e:
        print(f"Failed to update {model.__name__}: {e}")
        traceback.print_exc()
    finally:
        session.close()

def refresh_model_class(model_class, column_name=None, column_type=None, default=None, nullable=True):
    try:
        metadata.reflect(bind=engine)
        table_name = model_class.__tablename__
        table = metadata.tables[table_name]
        for column in table.columns:
            if not hasattr(model_class, column.name):
                setattr(model_class, column.name, Column(column.type, default=column.default, nullable=column.nullable))
        
        if column_name and column_type:
            setattr(model_class, column_name, Column(column_type, default=default, nullable=nullable))
    except Exception as e:
        print(f"Failed to refresh model class {model_class.__name__}: {e}")
        traceback.print_exc()

def register_model_defaults(model_name, column_name, default):
    if model_name not in model_column_defaults:
        model_column_defaults[model_name] = {}
    model_column_defaults[model_name][column_name] = default

def track_added_column(table_name, column_name, column_type, default=None, nullable=True, primary_key=False):
    global added_columns
    if table_name not in added_columns:
        added_columns[table_name] = []
    added_columns[table_name].append((column_name, column_type, default, nullable, primary_key))

def update_dynamic_models_from_added_columns():
    updated = False
    for table_name, columns in added_columns.items():
        class_name = get_model_class_by_table_name(table_name)
        if class_name:
            for column_name, column_type, default, nullable, primary_key in columns:
                update_dynamic_models_file(class_name.__name__, column_name, column_type, default, nullable, primary_key=primary_key)
                updated = True
    return updated

def init_db():
    try:
        check_and_generate_dynamic_models()
        from modules.dynamic_models import Base
        Base.metadata.create_all(bind=engine)
        metadata.reflect(bind=engine)
    except Exception as e:
        print(f"Failed to initialize the database: {e}")
        traceback.print_exc()

async def setup(bot, restart_fn):
    global restart_program_fn, bot_instance
    restart_program_fn = restart_fn
    bot_instance = bot
    try:
        init_db()
        await create_pending_tables()  # Ensure pending tables are created
        update_dynamic_models_from_added_columns()  # Update dynamic models with added columns
        from modules.dynamic_models import User, ServerUser, Server  # Ensure the dynamic models are imported here
    except Exception as e:
        print(f"Failed to setup database module: {e}")
        traceback.print_exc()


__intents__ = ["guilds", "members"]
__version__ = "1.0.0"
