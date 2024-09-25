from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime
from sqlalchemy import BigInteger
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text

class User(Base):
    __tablename__ = 'user'
    __table_args__ = {'extend_existing': True}
    discord_id = Column(String, default=None, nullable=False, primary_key=True)
    global_join_date = Column(DateTime, default=datetime.utcnow, nullable=False, )
    username = Column(String, default=None, nullable=False, )
    avatar = Column(Text, default=None, nullable=True, )
    account_creation_date = Column(DateTime, default=datetime.utcnow, nullable=False, )
class Server(Base):
    __tablename__ = 'server'
    __table_args__ = {'extend_existing': True}
    guild_id = Column(BigInteger, default=None, nullable=False, primary_key=True)
    guild_name = Column(Text, default=None, nullable=False, )
    guild_owner_id = Column(BigInteger, default=None, nullable=False, )
    guild_icon_url = Column(Text, default=None, nullable=True, )
    language = Column(String, default='en', nullable=True, )
class ServerUser(Base):
    __tablename__ = 'serveruser'
    __table_args__ = {'extend_existing': True}
    id = Column(String, default=None, nullable=False, primary_key=True)
    user_id = Column(String, default=None, nullable=False, )
    server_id = Column(BigInteger, default=None, nullable=False, )
    join_date = Column(DateTime, default=datetime.utcnow, nullable=False, )
class Pokedexentry(Base):
    __tablename__ = 'pokedexentry'
    name = Column(String, default=None, nullable=False, )
    type = Column(String, default=None, nullable=False, )
    description = Column(Text, default=None, nullable=True, )
    pokemon_id = Column(Integer, default=None, nullable=False, primary_key=True)
