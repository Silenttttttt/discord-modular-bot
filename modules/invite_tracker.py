# modules/invite_tracker.py

import discord
from discord.ext import commands
from discord import app_commands
from modules.dynamic_models import User, ServerUser
from modules.database import get_or_create, update_instance, add_column, SessionLocal
from sqlalchemy import Integer, BigInteger, Boolean, func
import traceback
import asyncio
import time

async def setup_invite_tracker_columns():
    await add_column('serveruser', 'invited_by', BigInteger, nullable=True)
    await add_column('serveruser', 'invites_count', Integer, default=0, nullable=False)
    await add_column('serveruser', 'left_guild', Boolean, default=False, nullable=False)
    await add_column('serveruser', 'left_invitees', Integer, default=0, nullable=False)
    await add_column('serveruser', 'stayed_invitees', Integer, default=0, nullable=False, final_column=True)

class InviteTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_uses = {}
        self.event_timestamps = {}

    async def update_invite_uses(self):
        for guild in self.bot.guilds:
            try:
                invites = await guild.invites()
                self.invite_uses[guild.id] = {invite.code: invite.uses for invite in invites}
            except discord.Forbidden:
                print(f"Missing permissions to fetch invites for guild: {guild.name} ({guild.id})")
            except Exception as e:
                print(f"An unexpected error occurred while updating invites for guild: {guild.name} ({guild.id}): {e}")

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.update_invite_uses()

    def debounce_event(self, event_key, cooldown=2):
        current_time = time.time()
        if event_key in self.event_timestamps:
            last_time = self.event_timestamps[event_key]
            if current_time - last_time < cooldown:
                return True
        self.event_timestamps[event_key] = current_time
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member):
        event_key = f"join-{member.id}"
        if self.debounce_event(event_key):
            return

        print(f"Joined {member.name}")

        try:
            guild = member.guild

            try:
                await asyncio.sleep(2)
                invites_after_join = await guild.invites()
            except discord.Forbidden:
                print(f"Missing permissions to fetch invites for guild: {guild.name} ({guild.id})")
                return
            except Exception as e:
                print(f"An unexpected error occurred while fetching invites for guild: {guild.name} ({guild.id}): {e}")
                return

            used_invite = None
            for invite in invites_after_join:
                try:
                    if self.invite_uses[guild.id][invite.code] < invite.uses:
                        used_invite = invite
                        break
                except KeyError:
                    await self.update_invite_uses()
                    if self.invite_uses[guild.id][invite.code] < invite.uses:
                        used_invite = invite
                        break

            if not used_invite:
                used_invite = max(invites_after_join, key=lambda inv: inv.uses)

            if used_invite:
                inviter = used_invite.inviter
                print(f'{member.name} joined using invite: {used_invite.code}, invited by: {inviter.name if inviter else "Unknown"}')

                # Ensure the invitee is created or retrieved
                db_user = await get_or_create(User, discord_id=member.id)

                inviter_id = inviter.id if inviter else None

                # Ensure the invitee ServerUser instance is created or retrieved
                server_user_data = {
                    'user_id': db_user.discord_id,
                    'server_id': guild.id,
                    'invited_by': inviter_id,
                }
                server_user = await get_or_create(ServerUser, **server_user_data)
                await update_instance(ServerUser, {'user_id': db_user.discord_id, 'server_id': guild.id}, left_guild=False)

                if inviter_id:
                    # Ensure the inviter ServerUser instance is created or retrieved
                    inviter_server_user = await get_or_create(ServerUser, user_id=inviter_id, server_id=guild.id)
                    await update_instance(ServerUser, {'user_id': inviter_id, 'server_id': guild.id},
                                          invites_count=inviter_server_user.invites_count + 1,
                                          stayed_invitees=inviter_server_user.stayed_invitees + 1)

                    # Logging the update
                    updated_inviter_server_user = await get_or_create(ServerUser, user_id=inviter_id, server_id=guild.id)

                # If invited_by was None initially, update it with the correct inviter_id
                if server_user.invited_by is None and inviter_id:
                    await update_instance(ServerUser, {'user_id': db_user.discord_id, 'server_id': guild.id}, invited_by=inviter_id)

            await self.update_invite_uses()

        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            traceback.print_exc()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        event_key = f"leave-{member.id}"
        if self.debounce_event(event_key):
            return

        print(f"Left {member.name}")

        try:
            server_user = await get_or_create(ServerUser, user_id=member.id, server_id=member.guild.id)
            if server_user:
                await update_instance(ServerUser, {'user_id': member.id, 'server_id': member.guild.id}, left_guild=True)

                if server_user.invited_by:
                    inviter_server_user = await get_or_create(ServerUser, user_id=server_user.invited_by, server_id=member.guild.id)
                    if inviter_server_user:
                        await update_instance(ServerUser, {'user_id': server_user.invited_by, 'server_id': member.guild.id},
                                              stayed_invitees=inviter_server_user.stayed_invitees - 1,
                                              left_invitees=inviter_server_user.left_invitees + 1)

                    # Logging the update
                    updated_inviter_server_user = await get_or_create(ServerUser, user_id=server_user.invited_by, server_id=member.guild.id)

        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            traceback.print_exc()

    @app_commands.command(name="leaderboard", description="Shows the invite leaderboard")
    @app_commands.describe(period="The period for the leaderboard: today, week, month, all_time", limit="Number of users to return")
    async def leaderboard(self, interaction: discord.Interaction, period: str = 'all_time', limit: int = 10):
        session = SessionLocal()
        try:
            guild_id = interaction.guild.id
            period_map = {
                'today': "today",
                'week': "this week",
                'month': "this month",
                'all_time': "all time"
            }
            period_text = period_map.get(period, "all time")

            filter_period = {
                'today': func.date(func.now()) == func.date(ServerUser.join_date),
                'week': func.strftime('%Y-%W', func.now()) == func.strftime('%Y-%W', ServerUser.join_date),
                'month': func.strftime('%Y-%m', func.now()) == func.strftime('%Y-%m', ServerUser.join_date),
                'all_time': True
            }[period]

            results = session.query(
                ServerUser.user_id,
                func.sum(ServerUser.invites_count).label('total_invites'),
                func.sum(ServerUser.stayed_invitees).label('stayed_invitees'),
                func.sum(ServerUser.left_invitees).label('left_invitees')
            ).filter(
                ServerUser.server_id == guild_id,
                filter_period
            ).group_by(ServerUser.user_id).order_by(func.sum(ServerUser.invites_count).desc()).limit(limit).all()

            embed = discord.Embed(title="📊 Invite Leaderboard", description=f"Top {limit} inviters for {period_text}", color=discord.Color.blue())

            for user_id, total_invites, stayed_invitees, left_invitees in results:
                member = interaction.guild.get_member(user_id)
                mention = member.mention if member else f"<@{user_id}>"
                embed.add_field(name=f"👤 {mention}", value=f"Invites: {total_invites} (Stayed: {stayed_invitees}, Left: {left_invitees})", inline=False)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            error_message = str(e)
            print(f"An error occurred: {error_message}")
            traceback.print_exc()
            embed = discord.Embed(title="Error", description="Failed to retrieve the leaderboard.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            session.close()

    @app_commands.command(name="manage_invites", description="Manage invites for a user")
    @app_commands.describe(user="The user to manage invites for")
    async def manage_invites(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Permission Denied", description="You are missing Administrator permission(s) to run this command.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.send_message(embed=await self.get_invite_embed(user), view=InviteManagerView(self, user))

    async def get_invite_embed(self, user: discord.Member):
        session = SessionLocal()
        try:
            server_user = session.query(ServerUser).filter_by(user_id=user.id, server_id=user.guild.id).first()
            if not server_user:
                return discord.Embed(title="Invite Manager", description=f"No invite data for {user.display_name}")
            
            embed = discord.Embed(title="🔧 Invite Manager", description=f"Invite data for {user.display_name}", color=discord.Color.green())
            embed.add_field(name="🎟️ Invites Count", value=server_user.invites_count, inline=True)
            embed.add_field(name="✅ Stayed Invitees", value=server_user.stayed_invitees, inline=True)
            embed.add_field(name="❌ Left Invitees", value=server_user.left_invitees, inline=True)
            return embed
        finally:
            session.close()

class InviteManagerView(discord.ui.View):
    def __init__(self, cog: InviteTracker, user: discord.Member):
        super().__init__(timeout=30)
        self.cog = cog
        self.user = user
        self.message = None  # Initialize message attribute

    @discord.ui.button(label="Reset Invites", style=discord.ButtonStyle.primary)
    async def reset_invites(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Permission Denied", description="You do not have permission to use this.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        session = SessionLocal()
        try:
            session.query(ServerUser).filter_by(user_id=self.user.id, server_id=self.user.guild.id).update({
                'invites_count': 0,
                'stayed_invitees': 0,
                'left_invitees': 0
            })
            session.commit()
            await interaction.response.edit_message(embed=await self.cog.get_invite_embed(self.user))
        finally:
            session.close()

    @discord.ui.button(label="Delete Invites", style=discord.ButtonStyle.danger)
    async def delete_invites(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            embed = discord.Embed(title="Permission Denied", description="You do not have permission to use this.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        session = SessionLocal()
        try:
            session.query(ServerUser).filter_by(user_id=self.user.id, server_id=self.user.guild.id).delete()
            session.commit()
            embed = discord.Embed(title="Invite Manager", description=f"Deleted invite data for {self.user.display_name}")
            await interaction.response.edit_message(embed=embed)
        finally:
            session.close()

    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)  # Fixing the message attribute

async def setup(bot, restart_fn):
    await setup_invite_tracker_columns()
    await bot.add_cog(InviteTracker(bot))
    await InviteTracker(bot).update_invite_uses()

__intents__ = ["guilds", "members"]
__dependencies__ = ["database"]
__version__ = "1.0.0"
