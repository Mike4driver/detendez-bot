import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

class LevelingCog(commands.Cog):
    """Leveling system for Discord servers"""
    
    def __init__(self, bot):
        self.bot = bot
        self.user_cooldowns = {}  # Track user message cooldowns
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Award XP for messages"""
        # Ignore bots and DMs
        if message.author.bot or not message.guild:
            return
        
        # Get guild configuration
        config = await self.bot.db.get_guild_config(message.guild.id)
        
        # Check if channel is excluded
        if config.get('excluded_channels'):
            excluded = config['excluded_channels'].split(',')
            if str(message.channel.id) in excluded:
                return
        
        # Check cooldown
        user_key = f"{message.author.id}_{message.guild.id}"
        current_time = time.time()
        cooldown = config.get('xp_cooldown', 60)
        
        if user_key in self.user_cooldowns:
            if current_time - self.user_cooldowns[user_key] < cooldown:
                return
        
        self.user_cooldowns[user_key] = current_time
        
        # Get user's current data
        user_data = await self.bot.db.get_user_level_data(message.author.id, message.guild.id)
        old_level = user_data['level'] if user_data else 1
        
        # Award XP
        xp_amount = config.get('xp_per_message', 15)
        await self.bot.db.update_user_xp(message.author.id, message.guild.id, xp_amount)
        
        # Check for level up
        new_data = await self.bot.db.get_user_level_data(message.author.id, message.guild.id)
        new_level = new_data['level']
        
        if new_level > old_level:
            await self._handle_level_up(message, new_level, config)
    
    async def _handle_level_up(self, message, new_level, config):
        """Handle level up notifications"""
        # Create level up embed
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=f"{message.author.mention} reached **Level {new_level}**!",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        
        # Send to configured channel or current channel
        channel_id = config.get('level_up_channel')
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass  # Fallback to current channel
            else:
                await message.channel.send(embed=embed)
        else:
            await message.channel.send(embed=embed)
    
    @app_commands.command(name="rank", description="Check your or another user's rank and level")
    @app_commands.describe(user="User to check rank for (optional)")
    async def rank(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Check user rank and level"""
        target_user = user or interaction.user
        
        # Get user data
        user_data = await self.bot.db.get_user_level_data(target_user.id, interaction.guild.id)
        
        if not user_data:
            embed = discord.Embed(
                title="No Data",
                description=f"{target_user.mention} has no XP data yet.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Get user's rank
        leaderboard = await self.bot.db.get_leaderboard(interaction.guild.id, 1000)
        rank = next((i+1 for i, entry in enumerate(leaderboard) if entry['user_id'] == target_user.id), "N/A")
        
        # Calculate XP needed for next level
        current_level = user_data['level']
        current_xp = user_data['xp']
        xp_for_current = self.bot.db.calculate_xp_for_level(current_level)
        xp_for_next = self.bot.db.calculate_xp_for_level(current_level + 1)
        xp_needed = xp_for_next - current_xp
        
        # Create embed
        embed = discord.Embed(
            title=f"📊 Rank for {target_user.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="Level", value=current_level, inline=True)
        embed.add_field(name="XP", value=f"{current_xp:,}", inline=True)
        embed.add_field(name="XP to Next Level", value=f"{xp_needed:,}", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="leaderboard", description="Show the server leaderboard")
    @app_commands.describe(limit="Number of users to show (default: 10, max: 50)")
    async def leaderboard(self, interaction: discord.Interaction, limit: Optional[int] = 10):
        """Show server leaderboard"""
        if limit > 50:
            limit = 50
        elif limit < 1:
            limit = 10
        
        # Get leaderboard data
        leaderboard_data = await self.bot.db.get_leaderboard(interaction.guild.id, limit)
        
        if not leaderboard_data:
            embed = discord.Embed(
                title="📊 Leaderboard",
                description="No users have earned XP yet!",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Create leaderboard embed
        embed = discord.Embed(
            title=f"📊 {interaction.guild.name} Leaderboard",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        
        description = ""
        for entry in leaderboard_data:
            user = self.bot.get_user(entry['user_id'])
            if user:
                rank_emoji = self._get_rank_emoji(entry['rank'])
                description += f"{rank_emoji} **{user.display_name}** - Level {entry['level']} ({entry['xp']:,} XP)\n"
        
        embed.description = description
        embed.set_footer(text=f"Showing top {len(leaderboard_data)} users")
        
        await interaction.response.send_message(embed=embed)
    
    def _get_rank_emoji(self, rank):
        """Get emoji for rank position"""
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        else:
            return f"{rank}."
    
    # Admin Commands
    @app_commands.command(name="setlevel", description="Set a user's level (Admin only)")
    @app_commands.describe(user="User to set level for", level="Level to set")
    @app_commands.default_permissions(administrator=True)
    async def setlevel(self, interaction: discord.Interaction, user: discord.Member, level: int):
        """Set user's level (Admin command)"""
        # Elevate if user has configured admin role
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        if level < 1:
            await interaction.response.send_message("Level must be at least 1!", ephemeral=True)
            return
        
        await self.bot.db.set_user_level(user.id, interaction.guild.id, level)
        
        embed = discord.Embed(
            title="✅ Level Set",
            description=f"Set {user.mention}'s level to **{level}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="addxp", description="Add XP to a user (Admin only)")
    @app_commands.describe(user="User to add XP to", amount="Amount of XP to add")
    @app_commands.default_permissions(administrator=True)
    async def addxp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Add XP to a user (Admin command)"""
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        if amount <= 0:
            await interaction.response.send_message("XP amount must be positive!", ephemeral=True)
            return
        
        # Get old level
        user_data = await self.bot.db.get_user_level_data(user.id, interaction.guild.id)
        old_level = user_data['level'] if user_data else 1
        
        await self.bot.db.update_user_xp(user.id, interaction.guild.id, amount)
        
        # Check for level up
        new_data = await self.bot.db.get_user_level_data(user.id, interaction.guild.id)
        new_level = new_data['level']
        
        embed = discord.Embed(
            title="✅ XP Added",
            description=f"Added **{amount:,} XP** to {user.mention}",
            color=discord.Color.green()
        )
        
        if new_level > old_level:
            embed.add_field(name="Level Up!", value=f"Level {old_level} → {new_level}", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="removexp", description="Remove XP from a user (Admin only)")
    @app_commands.describe(user="User to remove XP from", amount="Amount of XP to remove")
    @app_commands.default_permissions(administrator=True)
    async def removexp(self, interaction: discord.Interaction, user: discord.Member, amount: int):
        """Remove XP from a user (Admin command)"""
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        if amount <= 0:
            await interaction.response.send_message("XP amount must be positive!", ephemeral=True)
            return
        
        await self.bot.db.update_user_xp(user.id, interaction.guild.id, -amount)
        
        embed = discord.Embed(
            title="✅ XP Removed",
            description=f"Removed **{amount:,} XP** from {user.mention}",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="resetxp", description="Reset XP for a user or all users (Admin only)")
    @app_commands.describe(user="User to reset (leave empty to reset all)")
    @app_commands.default_permissions(administrator=True)
    async def resetxp(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """Reset XP for user or all users (Admin command)"""
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        await interaction.response.defer()
        
        if user:
            # Reset specific user
            await self.bot.db.set_user_level(user.id, interaction.guild.id, 1)
            embed = discord.Embed(
                title="✅ XP Reset",
                description=f"Reset XP for {user.mention}",
                color=discord.Color.orange()
            )
        else:
            # Reset all users - this requires a direct database operation
            import aiosqlite
            async with aiosqlite.connect(self.bot.db.db_file) as db:
                await db.execute(
                    'DELETE FROM user_levels WHERE guild_id = ?',
                    (interaction.guild.id,)
                )
                await db.commit()
            
            embed = discord.Embed(
                title="✅ XP Reset",
                description="Reset XP for all users in this server",
                color=discord.Color.orange()
            )
        
        await interaction.followup.send(embed=embed)
    
    # Configuration Commands
    @app_commands.command(name="leveling-config", description="Configure leveling system (Admin only)")
    @app_commands.describe(
        xp_per_message="XP awarded per message",
        cooldown="Cooldown between XP awards (seconds)",
        level_up_channel="Channel for level up notifications"
    )
    @app_commands.default_permissions(administrator=True)
    async def leveling_config(
        self, 
        interaction: discord.Interaction, 
        xp_per_message: Optional[int] = None,
        cooldown: Optional[int] = None,
        level_up_channel: Optional[discord.TextChannel] = None
    ):
        """Configure leveling system settings"""
        # Elevate if user has configured admin role
        config_all = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config_all.get('admin_role') if config_all else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        config_updates = {}
        
        if xp_per_message is not None:
            if xp_per_message < 1 or xp_per_message > 100:
                await interaction.response.send_message("XP per message must be between 1 and 100!", ephemeral=True)
                return
            config_updates['xp_per_message'] = xp_per_message
        
        if cooldown is not None:
            if cooldown < 0 or cooldown > 3600:
                await interaction.response.send_message("Cooldown must be between 0 and 3600 seconds!", ephemeral=True)
                return
            config_updates['xp_cooldown'] = cooldown
        
        if level_up_channel is not None:
            config_updates['level_up_channel'] = level_up_channel.id
        
        if not config_updates:
            # Show current configuration
            config = await self.bot.db.get_guild_config(interaction.guild.id)
            embed = discord.Embed(
                title="⚙️ Leveling Configuration",
                color=discord.Color.blue()
            )
            embed.add_field(name="XP per Message", value=config.get('xp_per_message', 15), inline=True)
            embed.add_field(name="Cooldown", value=f"{config.get('xp_cooldown', 60)}s", inline=True)
            
            channel_id = config.get('level_up_channel')
            if channel_id:
                channel = self.bot.get_channel(channel_id)
                channel_name = channel.mention if channel else "Deleted Channel"
            else:
                channel_name = "Same as message channel"
            embed.add_field(name="Level Up Channel", value=channel_name, inline=True)
            
            await interaction.response.send_message(embed=embed)
        else:
            # Update configuration
            await self.bot.db.update_guild_config(interaction.guild.id, **config_updates)
            
            embed = discord.Embed(
                title="✅ Configuration Updated",
                description="Leveling system configuration has been updated!",
                color=discord.Color.green()
            )
            
            for key, value in config_updates.items():
                if key == 'level_up_channel':
                    channel = self.bot.get_channel(value)
                    embed.add_field(name="Level Up Channel", value=channel.mention if channel else "Unknown", inline=True)
                elif key == 'xp_per_message':
                    embed.add_field(name="XP per Message", value=value, inline=True)
                elif key == 'xp_cooldown':
                    embed.add_field(name="Cooldown", value=f"{value}s", inline=True)
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(LevelingCog(bot)) 