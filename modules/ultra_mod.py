# modules/ultra_mod.py

import discord
from discord.ext import commands
from discord import app_commands
from modules.database import get_or_create, update_instance, add_column, SessionLocal
from modules.dynamic_models import User, ServerUser
from sqlalchemy import Column, Integer, Boolean, String
import traceback
from datetime import datetime
import asyncio

async def setup_server_user_columns():
    await add_column('serveruser', 'warnings', Integer, default=0, nullable=False)
    await add_column('serveruser', 'automod', Boolean, default=True, nullable=False)
    await add_column('serveruser', 'banned', Boolean, default=False, nullable=False)
    await add_column('serveruser', 'muted', Boolean, default=False, nullable=False)
    await add_column('serveruser', 'locked_out', Boolean, default=False, nullable=False)
    await add_column('serveruser', 'notes', String, default='', nullable=True, final_column=True)

class AdminUserView(discord.ui.View):
    def __init__(self, user: discord.Member, guild: discord.Guild):
        super().__init__(timeout=120)
        self.user = user
        self.guild = guild
        self.embed = None

    async def setup(self):
        await self.update_embed()

    async def get_user_data(self):
        return await get_or_create(User, discord_id=str(self.user.id))

    async def get_server_user_data(self):
        return await get_or_create(ServerUser, user_id=str(self.user.id), server_id=str(self.guild.id))

    def log_action(self, action: str):
        with open("admin_logs.txt", "a") as log_file:
            log_file.write(f"{datetime.utcnow()} - {action} - User: {self.user.id} ({self.user.display_name}) - Server: {self.guild.id}\n")

    async def ensure_role_exists(self, role_name: str, permissions: dict) -> discord.Role:
        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            role = await self.guild.create_role(name=role_name)
        for channel in self.guild.channels:
            await channel.set_permissions(role, overwrite=discord.PermissionOverwrite(**permissions))
        return role

    @discord.ui.button(label="🔨 Ban User", style=discord.ButtonStyle.danger, custom_id="ban_user", row=0)
    async def ban_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.guild.ban(self.user)
        await update_instance(ServerUser, {'user_id': str(self.user.id), 'server_id': str(self.guild.id)}, banned=True)
        self.log_action("Banned User")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="🔇 Mute User", style=discord.ButtonStyle.secondary, custom_id="mute_user", row=0)
    async def mute_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        mute_role = await self.ensure_role_exists("Muted", {'send_messages': False, 'speak': False})
        await self.user.add_roles(mute_role)
        await update_instance(ServerUser, {'user_id': str(self.user.id), 'server_id': str(self.guild.id)}, muted=True)
        self.log_action("Muted User")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="🚫 Kick User", style=discord.ButtonStyle.danger, custom_id="kick_user", row=0)
    async def kick_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.guild.kick(self.user)
        self.log_action("Kicked User")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="⚠️ Warn User", style=discord.ButtonStyle.secondary, custom_id="warn_user", row=0)
    async def warn_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_user_data = await self.get_server_user_data()
        new_warnings = server_user_data.warnings + 1
        await update_instance(ServerUser, {'user_id': str(self.user.id), 'server_id': str(self.guild.id)}, warnings=new_warnings)
        self.log_action(f"Warned User (Total warnings: {new_warnings})")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="🧹 Delete All Messages", style=discord.ButtonStyle.secondary, custom_id="delete_messages", row=1)
    async def delete_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        def is_user_message(msg):
            return msg.author == self.user
        deleted = await interaction.channel.purge(check=is_user_message)
        self.log_action(f"Deleted {len(deleted)} messages")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="🔒 Lock User Out", style=discord.ButtonStyle.danger, custom_id="lock_user", row=1)
    async def lock_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        lock_role = await self.ensure_role_exists("Locked Out", {'send_messages': False, 'speak': False, 'connect': False})
        await self.user.add_roles(lock_role)
        await update_instance(ServerUser, {'user_id': str(self.user.id), 'server_id': str(self.guild.id)}, locked_out=True)
        self.log_action("Locked User Out")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="⚙️ Toggle Automod", style=discord.ButtonStyle.primary, custom_id="toggle_automod", row=1)
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button):
        server_user_data = await self.get_server_user_data()
        new_status = not server_user_data.automod
        await update_instance(ServerUser, {'user_id': str(self.user.id), 'server_id': str(self.guild.id)}, automod=new_status)
        status = "enabled" if new_status else "disabled"
        self.log_action(f"Automod {status}")
        await self.update_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=self.embed, view=self)

    @discord.ui.button(label="➡️ Next Page", style=discord.ButtonStyle.secondary, custom_id="next_page", row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Next Page clicked!", ephemeral=True)

    @discord.ui.button(label="❎ Close", style=discord.ButtonStyle.danger, custom_id="close", row=2)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    @discord.ui.button(label="📝 Add Note", style=discord.ButtonStyle.secondary, custom_id="add_note", row=2)
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AddNoteModal(user_id=str(self.user.id), server_id=str(self.guild.id))
        await interaction.response.send_modal(modal)

    async def update_embed(self):
        user_data = await self.get_user_data()
        server_user_data = await self.get_server_user_data()
        date_joined = user_data.global_join_date.strftime("%Y-%m-%d")
        invited_by = await self.get_inviter(server_user_data.invited_by)
        warnings = server_user_data.warnings
        automod_status = "🟢 Enabled" if server_user_data.automod else "🔴 Disabled"
        muted_status = "🔇 Muted" if server_user_data.muted else "🔊 Not Muted"
        banned_status = "⛔ Banned" if server_user_data.banned else "✅ Not Banned"
        locked_out_status = "🔒 Locked Out" if server_user_data.locked_out else "🔓 Not Locked Out"
        notes = server_user_data.notes if server_user_data.notes else "No notes available"

        self.embed = discord.Embed(
            title=f"🔧 Admin User Panel - {self.user.display_name}",
            description="Manage the user's account and settings below.",
            color=discord.Color.blue()
        )
        self.embed.set_thumbnail(url=self.user.avatar.url)
        self.embed.add_field(name="👤 Username", value=self.user.mention, inline=True)
        self.embed.add_field(name="📅 Date Joined", value=date_joined, inline=True)
        self.embed.add_field(name="👥 Invited By", value=invited_by, inline=True)
        self.embed.add_field(name="⚠️ Warnings", value=warnings, inline=True)
        self.embed.add_field(name="🔧 Automod Status", value=automod_status, inline=True)
        self.embed.add_field(name="🔇 Muted Status", value=muted_status, inline=True)
        self.embed.add_field(name="⛔ Banned Status", value=banned_status, inline=True)
        self.embed.add_field(name="🔒 Locked Out Status", value=locked_out_status, inline=True)
        self.embed.add_field(name="📝 Notes", value=notes, inline=False)

    async def get_inviter(self, invited_by_id):
        if invited_by_id:
            session = SessionLocal()
            try:
                inviter_user = session.query(User).filter_by(discord_id=str(invited_by_id)).first()
                return inviter_user.username if inviter_user else "Unknown"
            except Exception as e:
                print(f"Failed to get inviter: {e}")
                traceback.print_exc()
                return "Unknown"
            finally:
                session.close()
        return "Unknown"

class AddNoteModal(discord.ui.Modal, title="Add Note"):
    note = discord.ui.TextInput(label="Note", style=discord.TextStyle.paragraph)

    def __init__(self, user_id: str, server_id: str):
        super().__init__()
        self.user_id = user_id
        self.server_id = server_id

    async def on_submit(self, interaction: discord.Interaction):
        server_user_data = await get_or_create(ServerUser, user_id=self.user_id, server_id=self.server_id)
        new_notes = (server_user_data.notes + "\n" if server_user_data.notes else "") + self.note.value
        await update_instance(ServerUser, {'user_id': self.user_id, 'server_id': self.server_id}, notes=new_notes)
        await interaction.response.send_message(f"Note added: {self.note.value}", ephemeral=True)

class UltraMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='admin', description='Administer a user')
    @app_commands.describe(user='The user to administer')
    async def admin(self, interaction: discord.Interaction, user: discord.Member):
        try:
            view = AdminUserView(user, interaction.guild)
            await view.setup()
            await interaction.response.send_message(embed=view.embed, view=view)
        except Exception as e:
            print(e)
            traceback.print_exc()

async def setup(bot, restart_fn):
    await setup_server_user_columns()  # Ensure the server user columns are set up
    await bot.add_cog(UltraMod(bot))

__dependencies__ = ["database", "invite_tracker"]
__version__ = "1.0.0"
