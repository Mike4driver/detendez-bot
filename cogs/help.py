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
        embed.add_field(
            name="📊 Leveling System",
            value="`/help leveling` - XP, ranks, leaderboards",
            inline=True
        )
        
        embed.add_field(
            name="⭐ Starboard",
            value="`/help starboard` - Star messages, highlights",
            inline=True
        )
        
        embed.add_field(
            name="🎵 Music Bot",
            value="`/help music` - Play music, queue management",
            inline=True
        )
        
        embed.add_field(
            name="🎂 Birthdays",
            value="`/help birthday` - Birthday tracking, announcements",
            inline=True
        )
        
        embed.add_field(
            name="🧠 Facts & Questions",
            value="`/help facts` or `/help questions` - Daily content",
            inline=True
        )
        
        embed.add_field(
            name="⚙️ Configuration",
            value="`/help config` - Admin settings",
            inline=True
        )
        
        embed.add_field(
            name="🗺️ Geographic Polls",
            value="`/help geographic` - US region polls",
            inline=True
        )
        
        embed.set_footer(text="Use /help <category> for detailed information about each feature")
        
        await interaction.response.send_message(embed=embed)
    
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
                "• Set optional birthday role"
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
            description="Daily interesting facts powered by AI!",
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
                "`/question-config` - Daily questions settings"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Permissions Required",
            value="All configuration commands require **Administrator** permission.",
            inline=False
        )
        
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