import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

class HelpCog(commands.Cog):
    """Help system for the bot"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="help", description="Show help information")
    @app_commands.describe(category="Specific category to get help for")
    async def help_command(self, interaction: discord.Interaction, category: Optional[str] = None):
        """Show help information"""
        
        if category:
            await self._show_category_help(interaction, category.lower())
        else:
            await self._show_main_help(interaction)
    
    async def _show_main_help(self, interaction: discord.Interaction):
        """Show main help menu"""
        embed = discord.Embed(
            title="🤖 DetendezBot Help",
            description="A multi-functional Discord bot with leveling, starboard, music, and more!",
            color=discord.Color.blue()
        )
        
        # Add category fields
        embed.add_field(name="📊 Leveling", value="`/help leveling`", inline=True)
        
        embed.add_field(name="⭐ Starboard", value="`/help starboard`", inline=True)
        
        embed.add_field(name="🎵 Music", value="`/help music`", inline=True)
        
        embed.add_field(name="🎂 Birthdays", value="`/help birthday`", inline=True)
        
        embed.add_field(name="🧠 Facts", value="`/help facts`", inline=True)
        embed.add_field(name="🤔 Questions", value="`/help questions`", inline=True)
        
        embed.add_field(name="🧙 D&D", value="`/help dnd`", inline=True)
        embed.add_field(name="🗺️ Geographic", value="`/help geographic`", inline=True)
        embed.add_field(name="🎤 TTS", value="`/help tts`", inline=True)
        embed.add_field(name="🖼️ Quotes", value="`/help quotes`", inline=True)
        embed.add_field(name="🗓️ Scheduler", value="`/help scheduler`", inline=True)
        embed.add_field(name="⚙️ Config", value="`/help config`", inline=True)
        
        embed.add_field(
            name="🗺️ Geographic Polls",
            value="`/help geographic` - US region polls",
            inline=True
        )
        
        embed.set_footer(text="Use /help <category> for detailed information about each feature")
        
        await interaction.response.send_message(embed=embed)

    async def _user_is_admin_or_role(self, interaction: discord.Interaction) -> bool:
        """Check if user has Administrator or configured admin role."""
        if interaction.user.guild_permissions.administrator:
            return True
        if hasattr(self.bot, 'db'):
            try:
                cfg = await self.bot.db.get_guild_config(interaction.guild.id)
            except Exception:
                # If database call fails, default to not elevating
                return False
            role_id = cfg.get('admin_role') if cfg else None
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in interaction.user.roles:
                    return True
        return False
    
    async def _show_category_help(self, interaction: discord.Interaction, category: str):
        """Show help for a specific category"""
        
        if category in ['leveling', 'levels', 'xp']:
            await self._show_leveling_help(interaction)
        elif category in ['starboard', 'star', 'stars']:
            await self._show_starboard_help(interaction)
        elif category in ['music', 'audio', 'play']:
            await self._show_music_help(interaction)
        elif category in ['birthday', 'birthdays']:
            await self._show_birthday_help(interaction)
        elif category in ['facts', 'fact']:
            await self._show_facts_help(interaction)
        elif category in ['questions', 'question']:
            await self._show_questions_help(interaction)
        elif category in ['dnd']:
            await self._show_dnd_help(interaction)
        elif category in ['tts']:
            await self._show_tts_help(interaction)
        elif category in ['quotes', 'quote']:
            await self._show_quotes_help(interaction)
        elif category in ['scheduler', 'schedule']:
            await self._show_scheduler_help(interaction)
        elif category in ['config', 'configuration', 'admin']:
            await self._show_config_help(interaction)
        elif category in ['geographic', 'geography', 'polls', 'region']:
            await self._show_geographic_help(interaction)
        else:
            embed = discord.Embed(
                title="❌ Unknown Category",
                description=f"Unknown help category: `{category}`\n\nUse `/help` to see available categories.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _show_leveling_help(self, interaction: discord.Interaction):
        """Show leveling system help"""
        embed = discord.Embed(
            title="📊 Leveling System Help",
            description="Earn XP by chatting and climb the server leaderboard!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="User Commands",
            value=(
                "`/rank [user]` - Check your or someone's rank and level\n"
                "`/leaderboard [limit]` - View the server leaderboard"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/setlevel <user> <level>` - Set a user's level\n"
                "`/addxp <user> <amount>` - Add XP to a user\n"
                "`/removexp <user> <amount>` - Remove XP from a user\n"
                "`/resetxp [user]` - Reset XP for user or all users\n"
                "`/leveling-config` - Configure leveling settings"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How it Works",
            value=(
                "• Earn XP by sending messages (default: 15 XP per message)\n"
                "• 60-second cooldown prevents spam\n"
                "• Level formula: 5 × (level²) + 50 × level + 100\n"
                "• Automatic level-up notifications"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_starboard_help(self, interaction: discord.Interaction):
        """Show starboard help"""
        embed = discord.Embed(
            title="⭐ Starboard Help",
            description="Highlight the best messages in your server!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="User Commands",
            value=(
                "`/starboard` - View current starboard configuration\n"
                "`/star <message_id>` - Manually add a message to starboard"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/starboard-config` - Configure starboard settings\n"
                "• Set starboard channel\n"
                "• Change star emoji (default: ⭐)\n"
                "• Set star threshold (default: 3 stars)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="How it Works",
            value=(
                "• React to messages with the star emoji\n"
                "• When threshold is reached, message appears in starboard\n"
                "• Star count updates automatically\n"
                "• Users can't star their own messages\n"
                "• Messages below threshold are removed"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_music_help(self, interaction: discord.Interaction):
        """Show music bot help"""
        embed = discord.Embed(
            title="🎵 Music Bot Help",
            description="Play music from YouTube in voice channels!",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Playback Commands",
            value=(
                "`/play <query>` - Play a song or add to queue\n"
                "`/pause` - Pause the current song\n"
                "`/resume` - Resume the paused song\n"
                "`/skip` - Skip the current song\n"
                "`/stop` - Stop music and disconnect"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Queue Commands",
            value=(
                "`/queue` - Show the current music queue\n"
                "`/remove <position>` - Remove a song from queue\n"
                "`/nowplaying` or `/np` - Show current song info"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Other Commands",
            value=(
                "`/volume <0-100>` - Set playback volume"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• YouTube search and direct links\n"
                "• Automatic queue progression\n"
                "• Auto-disconnect after 5 minutes of inactivity\n"
                "• Per-server volume control"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_birthday_help(self, interaction: discord.Interaction):
        """Show birthday system help"""
        embed = discord.Embed(
            title="🎂 Birthday System Help",
            description="Track birthdays and celebrate with your community!",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="User Commands",
            value=(
                "`/setbirthday <date>` - Set your birthday (MM/DD or 'Month Day')\n"
                "`/birthday [user]` - View someone's birthday\n"
                "`/birthdays [month]` - List birthdays for a month\n"
                "`/removebirthday` - Remove your birthday"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/birthday-config` - Configure birthday settings\n"
                "• Set birthday announcement channel\n"
                "• Set optional birthday role\n"
                "• Set permanent birthday post channel\n"
                "`/refresh-birthday-post` - Rebuild the permanent birthday post"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• Automatic daily birthday announcements\n"
                "• Optional temporary birthday role\n"
                "• Support for MM/DD and 'Month Day' formats\n"
                "• Countdown to next birthday"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_facts_help(self, interaction: discord.Interaction):
        """Show facts system help"""
        embed = discord.Embed(
            title="🧠 Facts System Help",
            description="Daily interesting facts powered by Beanz!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="User Commands",
            value="`/fact` - Get a random fun fact",
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/fact-config` - Configure fact settings\n"
                "• Set fact channel\n"
                "• Set daily fact time"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• AI-generated interesting facts\n"
                "• Daily automatic posting\n"
                "• Avoids repetition for 7 days\n"
                "• Fallback facts if AI is unavailable"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_questions_help(self, interaction: discord.Interaction):
        """Show questions system help"""
        embed = discord.Embed(
            title="🤔 Questions System Help",
            description="Daily discussion questions to engage your community!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="User Commands",
            value="`/question` - Get a random discussion question",
            inline=False
        )
        
        embed.add_field(
            name="Admin Commands",
            value=(
                "`/question-config` - Configure question settings\n"
                "• Set question channel\n"
                "• Set daily question time"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Features",
            value=(
                "• AI-generated thought-provoking questions\n"
                "• Daily automatic posting\n"
                "• Automatic reaction to encourage participation\n"
                "• Variety of question types and topics"
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    async def _show_dnd_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🧙 D&D Tools",
            description="Dice rolling and action parsing",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/roll <XdY[+/-Z]>` - Roll dice\n"
                "`/dnd-action <action>` - Parse an action (e.g., 'level 3 smite') and roll\n"
                "`/dnd-help <question>` - Get concise 5e guidance"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    async def _show_tts_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎤 Text-to-Speech",
            description="ElevenLabs-powered TTS",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/tts <text> [voice] [model]` - Generate TTS audio\n"
                "`/voices` - List available voices\n"
                "`/tts-models` - List available models\n"
                "`/tts-config` - Configure TTS (admin)"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    async def _show_quotes_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🖼️ Quotes",
            description="Generate quote images",
            color=discord.Color.teal()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/quote <text> <@author>` - Quote with member author\n"
                "`/quote-text <text> <author_name>` - Quote with custom author"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)

    async def _show_scheduler_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🗓️ Scheduler",
            description="Create Discord scheduled events from natural language",
            color=discord.Color.dark_teal()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/schedule <prompt> [timezone]` - Create an event with GCal/ICS links"
            ),
            inline=False
        )
        await interaction.response.send_message(embed=embed)
    
    async def _show_config_help(self, interaction: discord.Interaction):
        """Show configuration help"""
        embed = discord.Embed(
            title="⚙️ Configuration Help",
            description="Admin commands to configure bot features",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Leveling Configuration",
            value=(
                "`/leveling-config` - Configure XP settings\n"
                "• XP per message amount\n"
                "• Cooldown between XP awards\n"
                "• Level-up notification channel"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Starboard Configuration",
            value=(
                "`/starboard-config` - Configure starboard\n"
                "• Starboard channel\n"
                "• Star emoji\n"
                "• Star threshold"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Other Configurations",
            value=(
                "`/birthday-config` - Birthday settings\n"
                "`/fact-config` - Daily facts settings\n"
                "`/question-config` - Daily questions settings\n"
                "`/tts-config` - TTS settings\n"
                "`/admin-role <role>` - Set an Admin Role for bot commands\n"
                "`/config` - View all current configurations"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Permissions",
            value=(
                "Admin commands accept **Administrator** or the configured **Admin Role**.\n"
                "Set with `/admin-role <role>`."
            ),
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="admin-role", description="Set a role that can use admin bot commands (Admin only)")
    @app_commands.describe(role="Role to grant admin command access")
    @app_commands.default_permissions(administrator=True)
    async def set_admin_role(self, interaction: discord.Interaction, role: discord.Role):
        # Only server admins can set this; no elevation here to avoid lockout
        await self.bot.db.update_guild_config(interaction.guild.id, admin_role=role.id)
        embed = discord.Embed(
            title="✅ Admin Role Updated",
            description=f"Set admin role to {role.mention}. Members with this role can use bot admin commands.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="config", description="View all bot configurations for this server (Admin only)")
    async def view_config(self, interaction: discord.Interaction):
        """View all bot configurations for the server"""
        # Elevate if user has configured admin role
        config = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return
        
        embed = discord.Embed(
            title="⚙️ Bot Configuration",
            description=f"All configured settings for **{interaction.guild.name}**",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        
        # Admin Role
        admin_role_id = config.get('admin_role')
        if admin_role_id:
            admin_role = interaction.guild.get_role(admin_role_id)
            admin_role_text = admin_role.mention if admin_role else "Deleted Role"
        else:
            admin_role_text = "Not configured"
        embed.add_field(name="🔐 Admin Role", value=admin_role_text, inline=True)
        
        # Leveling Configuration
        xp_per_message = config.get('xp_per_message', 15)
        xp_cooldown = config.get('xp_cooldown', 60)
        level_up_channel_id = config.get('level_up_channel')
        if level_up_channel_id:
            level_up_channel = self.bot.get_channel(level_up_channel_id)
            level_up_text = level_up_channel.mention if level_up_channel else "Deleted Channel"
        else:
            level_up_text = "Not configured"
        
        leveling_value = (
            f"**XP per Message:** {xp_per_message}\n"
            f"**Cooldown:** {xp_cooldown}s\n"
            f"**Level-up Channel:** {level_up_text}"
        )
        embed.add_field(name="📊 Leveling", value=leveling_value, inline=False)
        
        # Starboard Configuration
        starboard_channel_id = config.get('starboard_channel')
        star_threshold = config.get('star_threshold', 3)
        star_emoji = config.get('star_emoji', '⭐')
        if starboard_channel_id:
            starboard_channel = self.bot.get_channel(starboard_channel_id)
            starboard_text = starboard_channel.mention if starboard_channel else "Deleted Channel"
        else:
            starboard_text = "Not configured"
        
        starboard_value = (
            f"**Channel:** {starboard_text}\n"
            f"**Threshold:** {star_threshold} {star_emoji}\n"
            f"**Emoji:** {star_emoji}"
        )
        embed.add_field(name="⭐ Starboard", value=starboard_value, inline=False)
        
        # Birthday Configuration
        birthday_channel_id = config.get('birthday_channel')
        birthday_role_id = config.get('birthday_role')
        birthday_permanent_channel_id = config.get('birthday_permanent_channel')
        birthday_time = config.get('birthday_time', '00:00')
        
        if birthday_channel_id:
            birthday_channel = self.bot.get_channel(birthday_channel_id)
            birthday_channel_text = birthday_channel.mention if birthday_channel else "Deleted Channel"
        else:
            birthday_channel_text = "Not configured"
        
        if birthday_role_id:
            birthday_role = interaction.guild.get_role(birthday_role_id)
            birthday_role_text = birthday_role.mention if birthday_role else "Deleted Role"
        else:
            birthday_role_text = "Not configured"
        
        if birthday_permanent_channel_id:
            permanent_channel = self.bot.get_channel(birthday_permanent_channel_id)
            permanent_text = permanent_channel.mention if permanent_channel else "Deleted Channel"
        else:
            permanent_text = "Not configured"
        
        birthday_value = (
            f"**Announcement Channel:** {birthday_channel_text}\n"
            f"**Birthday Role:** {birthday_role_text}\n"
            f"**Permanent Post Channel:** {permanent_text}\n"
            f"**Announcement Time:** {birthday_time}"
        )
        embed.add_field(name="🎂 Birthdays", value=birthday_value, inline=False)
        
        # Facts Configuration
        fact_channel_id = config.get('fact_channel')
        fact_time = config.get('fact_time', '09:00')
        if fact_channel_id:
            fact_channel = self.bot.get_channel(fact_channel_id)
            fact_channel_text = fact_channel.mention if fact_channel else "Deleted Channel"
        else:
            fact_channel_text = "Not configured"
        
        embed.add_field(name="🧠 Daily Facts", value=f"**Channel:** {fact_channel_text}\n**Time:** {fact_time}", inline=True)
        
        # Questions Configuration
        question_channel_id = config.get('question_channel')
        question_time = config.get('question_time', '15:00')
        if question_channel_id:
            question_channel = self.bot.get_channel(question_channel_id)
            question_channel_text = question_channel.mention if question_channel else "Deleted Channel"
        else:
            question_channel_text = "Not configured"
        
        embed.add_field(name="🤔 Daily Questions", value=f"**Channel:** {question_channel_text}\n**Time:** {question_time}", inline=True)
        
        # TTS Configuration (global, from Config)
        from config import Config
        tts_value = (
            f"**Max Length:** {Config.MAX_TTS_LENGTH} characters\n"
            f"**Default Voice:** {Config.DEFAULT_TTS_VOICE}\n"
            f"**Default Model:** {Config.DEFAULT_TTS_MODEL}"
        )
        embed.add_field(name="🎤 TTS (Global)", value=tts_value, inline=False)
        
        # Music Cookie Status
        import os
        cookie_file = "youtube_cookies.txt"
        cookie_exists = os.path.exists(cookie_file)
        cookie_status = "✅ Configured" if cookie_exists else "❌ Not configured"
        embed.add_field(name="🎵 Music Cookies", value=cookie_status, inline=True)
        
        embed.set_footer(text="Use individual config commands to modify settings")
        
        await interaction.response.send_message(embed=embed)
    
    async def _show_geographic_help(self, interaction: discord.Interaction):
        """Show geographic polls help"""
        embed = discord.Embed(
            title="🗺️ Geographic Polls Help",
            description="Create polls to see where users are from in the US!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="User Commands",
            value=(
                "`/geographic-poll [title] [description]` - Create a geographic poll\n"
                "`/geographic-results <message_id>` - View poll results\n"
                "`/my-region` - Check your region selections"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Regions",
            value=(
                "🌊 **West Coast** - California, Oregon, Washington\n"
                "🏙️ **East Coast** - New York, Florida, Maine, etc.\n"
                "🏔️ **North** - Alaska, Minnesota, North Dakota, etc.\n"
                "🌵 **South** - Texas, Arizona, Nevada, etc."
            ),
            inline=False
        )
        
        embed.add_field(
            name="How it Works",
            value=(
                "• Create a poll with `/geographic-poll`\n"
                "• Users react with their region emoji\n"
                "• Only one region can be selected per poll\n"
                "• View results with `/geographic-results`\n"
                "• Check your selections with `/my-region`"
            ),
            inline=False
        )
        
        embed.set_footer(text="Perfect for understanding your community's geographic diversity!")
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(HelpCog(bot)) 