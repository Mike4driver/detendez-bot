import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from typing import Optional

class StarboardCog(commands.Cog):
    """Starboard system for Discord servers"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle star reactions being added"""
        await self._handle_reaction_change(payload, added=True)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle star reactions being removed"""
        await self._handle_reaction_change(payload, added=False)
    
    async def _handle_reaction_change(self, payload, added=True):
        """Handle star reaction changes"""
        # Ignore DMs and bot reactions
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        # Get guild configuration
        config = await self.bot.db.get_guild_config(guild.id)
        star_emoji = config.get('star_emoji', '⭐')
        star_threshold = config.get('star_threshold', 3)
        starboard_channel_id = config.get('starboard_channel')
        
        if not starboard_channel_id:
            return  # No starboard channel configured
        
        # Check if this is the star emoji
        if str(payload.emoji) != star_emoji:
            return
        
        starboard_channel = self.bot.get_channel(starboard_channel_id)
        if not starboard_channel:
            return
        
        # Get the original message
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
        
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return
        
        # Don't allow self-starring
        user = guild.get_member(payload.user_id)
        if user and user.id == message.author.id:
            try:
                await message.remove_reaction(payload.emoji, user)
            except discord.Forbidden:
                pass
            return
        
        # Don't star bot messages or messages in starboard channel
        if message.author.bot or channel.id == starboard_channel_id:
            return
        
        # Count current stars
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == star_emoji:
                star_count = reaction.count
                # Subtract 1 if the message author reacted (shouldn't count)
                async for user in reaction.users():
                    if user.id == message.author.id:
                        star_count -= 1
                        break
                break
        
        # Handle starboard logic
        existing_starboard = await self.bot.db.get_starboard_message(message.id, guild.id)
        
        if star_count >= star_threshold:
            if existing_starboard:
                # Update existing starboard message
                await self._update_starboard_message(
                    starboard_channel, existing_starboard['starboard_message_id'], 
                    message, star_count
                )
                await self.bot.db.update_starboard_count(message.id, guild.id, star_count)
            else:
                # Create new starboard message
                starboard_message = await self._create_starboard_message(starboard_channel, message, star_count)
                if starboard_message:
                    await self.bot.db.add_starboard_message(
                        message.id, starboard_message.id, guild.id, star_count
                    )
        elif existing_starboard and star_count < star_threshold:
            # Remove from starboard if below threshold
            try:
                starboard_message = await starboard_channel.fetch_message(existing_starboard['starboard_message_id'])
                await starboard_message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            
            await self.bot.db.remove_starboard_message(message.id, guild.id)
    
    async def _create_starboard_message(self, starboard_channel, original_message, star_count):
        """Create a new starboard message"""
        try:
            embed = await self._create_starboard_embed(original_message, star_count)
            
            # Try to include original message content if it exists
            content = f"⭐ **{star_count}** {starboard_channel.mention}"
            
            starboard_message = await starboard_channel.send(content=content, embed=embed)
            return starboard_message
        except discord.Forbidden:
            return None
    
    async def _update_starboard_message(self, starboard_channel, starboard_message_id, original_message, star_count):
        """Update an existing starboard message"""
        try:
            starboard_message = await starboard_channel.fetch_message(starboard_message_id)
            embed = await self._create_starboard_embed(original_message, star_count)
            
            content = f"⭐ **{star_count}** {starboard_channel.mention}"
            
            await starboard_message.edit(content=content, embed=embed)
        except (discord.NotFound, discord.Forbidden):
            # Message was deleted, clean up database
            await self.bot.db.remove_starboard_message(original_message.id, original_message.guild.id)
    
    async def _create_starboard_embed(self, message, star_count):
        """Create embed for starboard message"""
        embed = discord.Embed(
            description=message.content[:2048] if message.content else "*No content*",
            color=discord.Color.gold(),
            timestamp=message.created_at
        )
        
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        
        embed.add_field(
            name="Source",
            value=f"[Jump to message]({message.jump_url})",
            inline=False
        )
        
        # Add image if present
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.content_type and attachment.content_type.startswith('image/'):
                embed.set_image(url=attachment.url)
        
        embed.set_footer(text=f"#{message.channel.name} • ⭐ {star_count}")
        
        return embed
    
    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        """Handle original message deletion"""
        if not payload.guild_id:
            return
        
        # Check if this message was on the starboard
        existing_starboard = await self.bot.db.get_starboard_message(payload.message_id, payload.guild_id)
        
        if existing_starboard:
            guild = self.bot.get_guild(payload.guild_id)
            config = await self.bot.db.get_guild_config(guild.id)
            starboard_channel_id = config.get('starboard_channel')
            
            if starboard_channel_id:
                starboard_channel = self.bot.get_channel(starboard_channel_id)
                if starboard_channel:
                    try:
                        starboard_message = await starboard_channel.fetch_message(existing_starboard['starboard_message_id'])
                        await starboard_message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
            
            await self.bot.db.remove_starboard_message(payload.message_id, payload.guild_id)
    
    # Configuration Commands
    @app_commands.command(name="starboard", description="Configure starboard settings")
    async def starboard_group(self, interaction: discord.Interaction):
        """Base starboard command - shows current config"""
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        
        embed = discord.Embed(
            title="⭐ Starboard Configuration",
            color=discord.Color.gold()
        )
        
        # Starboard channel
        starboard_channel_id = config.get('starboard_channel')
        if starboard_channel_id:
            channel = self.bot.get_channel(starboard_channel_id)
            channel_text = channel.mention if channel else "Deleted Channel"
        else:
            channel_text = "Not configured"
        embed.add_field(name="Starboard Channel", value=channel_text, inline=True)
        
        # Star emoji
        star_emoji = config.get('star_emoji', '⭐')
        embed.add_field(name="Star Emoji", value=star_emoji, inline=True)
        
        # Star threshold
        star_threshold = config.get('star_threshold', 3)
        embed.add_field(name="Star Threshold", value=star_threshold, inline=True)
        
        embed.set_footer(text="Use /starboard-config to modify these settings")
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="starboard-config", description="Configure starboard settings (Admin only)")
    @app_commands.describe(
        channel="Channel for starboard messages",
        emoji="Emoji to use for starring (default: ⭐)",
        threshold="Number of stars required for starboard"
    )
    async def starboard_config(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        emoji: Optional[str] = None,
        threshold: Optional[int] = None
    ):
        """Configure starboard settings"""
        # Elevate if user has configured admin role
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return

        config_updates = {}
        
        if channel is not None:
            # Check if bot has permissions in the channel
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "I don't have permission to send messages in that channel!", 
                    ephemeral=True
                )
                return
            config_updates['starboard_channel'] = channel.id
        
        if emoji is not None:
            # Validate emoji (basic check)
            if len(emoji) > 20:  # Arbitrary limit for custom emojis
                await interaction.response.send_message("Invalid emoji!", ephemeral=True)
                return
            config_updates['star_emoji'] = emoji
        
        if threshold is not None:
            if threshold < 1 or threshold > 50:
                await interaction.response.send_message(
                    "Star threshold must be between 1 and 50!", 
                    ephemeral=True
                )
                return
            config_updates['star_threshold'] = threshold
        
        if not config_updates:
            await interaction.response.send_message(
                "Please specify at least one setting to update!", 
                ephemeral=True
            )
            return
        
        # Update configuration
        await self.bot.db.update_guild_config(interaction.guild.id, **config_updates)
        
        embed = discord.Embed(
            title="✅ Starboard Configuration Updated",
            color=discord.Color.green()
        )
        
        for key, value in config_updates.items():
            if key == 'starboard_channel':
                channel_obj = self.bot.get_channel(value)
                embed.add_field(name="Starboard Channel", value=channel_obj.mention if channel_obj else "Unknown", inline=True)
            elif key == 'star_emoji':
                embed.add_field(name="Star Emoji", value=value, inline=True)
            elif key == 'star_threshold':
                embed.add_field(name="Star Threshold", value=value, inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="star", description="Manually star a message")
    @app_commands.describe(message_id="ID of the message to star")
    async def manual_star(self, interaction: discord.Interaction, message_id: str):
        """Manually add a message to starboard"""
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID!", ephemeral=True)
            return
        
        # Try to find the message in the current channel first
        try:
            message = await interaction.channel.fetch_message(msg_id)
        except discord.NotFound:
            # Search other channels (this is expensive, so limit it)
            message = None
            for channel in interaction.guild.text_channels:
                if channel.permissions_for(interaction.guild.me).read_message_history:
                    try:
                        message = await channel.fetch_message(msg_id)
                        break
                    except discord.NotFound:
                        continue
        
        if not message:
            await interaction.response.send_message("Message not found!", ephemeral=True)
            return
        
        # Get configuration
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        starboard_channel_id = config.get('starboard_channel')
        
        if not starboard_channel_id:
            await interaction.response.send_message("Starboard channel not configured!", ephemeral=True)
            return
        
        starboard_channel = self.bot.get_channel(starboard_channel_id)
        if not starboard_channel:
            await interaction.response.send_message("Starboard channel not found!", ephemeral=True)
            return
        
        # Check if already on starboard
        existing = await self.bot.db.get_starboard_message(message.id, interaction.guild.id)
        if existing:
            await interaction.response.send_message("Message is already on the starboard!", ephemeral=True)
            return
        
        # Create starboard entry
        starboard_message = await self._create_starboard_message(starboard_channel, message, 1)
        if starboard_message:
            await self.bot.db.add_starboard_message(message.id, starboard_message.id, interaction.guild.id, 1)
            await interaction.response.send_message("Message added to starboard!", ephemeral=True)
        else:
            await interaction.response.send_message("Failed to add message to starboard!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StarboardCog(bot)) 