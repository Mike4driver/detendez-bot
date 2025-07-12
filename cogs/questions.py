from asyncio.log import logger
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time
from typing import Optional
import google.generativeai as genai
from config import Config
import asyncio
import random

class QuestionsCog(commands.Cog):
    """Question of the day functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.setup_ai()
        self.daily_question.start()
    
    def setup_ai(self):
        """Setup Gemini AI"""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False
            print("Warning: Gemini API key not configured. Questions feature disabled.")
    
    def cog_unload(self):
        self.daily_question.cancel()
    
    async def _has_posted_today(self, guild_id: int, content_type: str) -> bool:
        """Check if content of a certain type has been posted today for a guild."""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute('''
                SELECT 1 FROM recent_content 
                WHERE guild_id = ? 
                AND content_type = ? 
                AND posted_date = DATE('now')
                LIMIT 1
            ''', (guild_id, content_type)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    @tasks.loop(minutes=1)
    async def daily_question(self):
        """Post daily questions to configured channels at the configured time."""
        now = datetime.now()
        current_time = time(now.hour, now.minute)

        for guild in self.bot.guilds:
            try:
                config = await self.bot.db.get_guild_config(guild.id)
                question_channel_id = config.get('question_channel')
                
                if not question_channel_id:
                    continue

                question_time_str = config.get('question_time', '15:00')
                
                try:
                    hour, minute = map(int, question_time_str.split(':'))
                    target_time = time(hour, minute)
                except (ValueError, AttributeError):
                    target_time = time(15, 0)
                
                if current_time == target_time:
                    if not await self._has_posted_today(guild.id, 'question'):
                        channel = self.bot.get_channel(question_channel_id)
                        if channel:
                            question = await self._generate_question()
                            if question:
                                embed = discord.Embed(
                                    title="🤔 Question of the Day",
                                    description=question,
                                    color=discord.Color.green(),
                                    timestamp=datetime.utcnow()
                                )
                                embed.set_footer(text="Daily question powered by AI")
                                
                                try:
                                    message = await channel.send(embed=embed)
                                    await message.add_reaction('🤔')
                                    await self._store_recent_content(guild.id, question)
                                except discord.Forbidden:
                                    logger.warning(f"No permission in channel {question_channel_id} for guild {guild.id}")
            
            except Exception as e:
                logger.error(f"Error in daily_question loop for guild {guild.id}: {e}")
    
    @daily_question.before_loop
    async def before_daily_question(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
    
    async def _generate_question(self) -> Optional[str]:
        """Generate a thought-provoking question using AI"""
        if not self.ai_enabled:
            return self._get_fallback_question()
        
        try:
            prompts = [
                "Generate a thought-provoking discussion question about personal growth, relationships, or life experiences. Make it engaging and suitable for a diverse community. Keep it under 250 characters.",
                "Create an interesting 'would you rather' or hypothetical question that encourages discussion. Make it fun and appropriate for all ages. Keep it concise (under 250 characters).",
                "Ask a creative question about dreams, goals, preferences, or opinions that people would enjoy answering. Make it engaging and inclusive. Keep it brief (under 250 characters).",
                "Generate a philosophical or reflective question about society, technology, or human nature. Make it thought-provoking but accessible. Keep it short (under 250 characters).",
                "Create a fun question about favorites, experiences, or 'what if' scenarios that sparks conversation. Make it interesting and appropriate for everyone. Keep it under 250 characters.",
                "Ask a nostalgic question about childhood, memories, or past experiences that people can relate to and share. Make it warm and inclusive. Keep it under 250 characters.",
                "Generate a creative question about imagination, storytelling, or fictional scenarios. Make it fun and spark creativity in responses. Keep it concise (under 250 characters).",
                "Create a question about hobbies, talents, or skills that encourages people to share their interests and learn about others. Make it engaging. Keep it brief (under 250 characters).",
                "Ask a lighthearted question about food, travel, or cultural experiences that brings people together. Make it appetizing for discussion! Keep it short (under 250 characters).",
                "Generate a question about problem-solving, decision-making, or life advice that invites wisdom sharing. Make it thoughtful and helpful. Keep it under 250 characters.",
                "Create a fun icebreaker question about random preferences, quirks, or interesting choices. Make it silly but engaging for all. Keep it concise (under 250 characters).",
                "Ask a question about creativity, art, music, or self-expression that celebrates different forms of creativity. Make it inspiring. Keep it brief (under 250 characters).",
                "Generate a community-building question about friendship, teamwork, or social connections. Make it inclusive and relationship-focused. Keep it short (under 250 characters).",
                "Create a question about learning, knowledge, or curiosity that encourages intellectual discussion. Make it educational but accessible. Keep it under 250 characters.",
                "Ask a seasonal or timely question related to current events, holidays, or time of year. Make it relevant and engaging for the moment. Keep it concise (under 250 characters).",
                "Generate a motivational question about challenges, achievements, or overcoming obstacles. Make it uplifting and encouraging. Keep it brief (under 250 characters)."
            ]
            
            prompt = random.choice(prompts)
            # Check for recent questions to avoid repetition
            recent_questions = await self._get_recent_questions()
            if recent_questions:
                prompt += f"\n\nAvoid these recently posted questions: {'; '.join(recent_questions)}"
            
            response = await asyncio.to_thread(
                self.model.generate_content, prompt
            )
            
            question = response.text.strip()
            # Basic validation and cleanup
            if len(question) > 300:
                question = question[:297] + "..."
            
            # Ensure it ends with a question mark
            if not question.endswith('?'):
                question += '?'
            
            return question
            
        except Exception as e:
            print(f"Error generating question: {e}")
            return self._get_fallback_question()
    
    def _get_fallback_question(self) -> str:
        """Get a fallback question when AI is unavailable"""
        questions = [
            "If you could have dinner with anyone (living or historical), who would it be and why?",
            "What's a skill you've always wanted to learn but haven't had the chance to try yet?",
            "Would you rather have the ability to fly or be invisible? Why?",
            "What's the best piece of advice you've ever received?",
            "If you could visit any place in the world, where would you go and what would you do there?",
            "What's something small that always makes you smile?",
            "If you could solve one world problem, what would it be?",
            "What's your favorite way to spend a rainy day?",
            "If you could time travel, would you go to the past or the future? Why?",
            "What's a book, movie, or show that changed your perspective on something?",
            "If you could have any superpower for just one day, what would you choose?",
            "What's the most interesting place you've ever visited?",
            "Would you rather always know the truth or always be happy? Why?",
            "What's something you're grateful for today?",
            "If you could master any instrument overnight, which would you choose?",
            "What's the best compliment you've ever received?",
            "If you could create a new holiday, what would it celebrate?",
            "What's something that seemed impossible but you achieved anyway?"
        ]
        return random.choice(questions)
    
    async def _store_recent_content(self, guild_id: int, content: str):
        logger.info(f"Storing recent content for guild {guild_id}: {content}")
        """Store recently posted content to avoid repetition"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO recent_content (guild_id, content_type, content, posted_date)
                VALUES (?, 'question', ?, DATE('now'))
            ''', (guild_id, content))
            
            # Clean up old content (keep only last 30 days)
            await db.execute('''
                DELETE FROM recent_content 
                WHERE content_type = 'question' 
                AND guild_id = ? 
                AND posted_date < DATE('now', '-30 days')
            ''', (guild_id,))
            
            await db.commit()
    
    async def _get_recent_questions(self) -> list:
        """Get recently posted questions to avoid repetition"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute('''
                SELECT content FROM recent_content 
                WHERE content_type = 'question' 
                AND posted_date > DATE('now', '-7 days')
                ORDER BY posted_date DESC
                LIMIT 50
            ''') as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    @app_commands.command(name="question", description="Get a random discussion question")
    async def question_command(self, interaction: discord.Interaction):
        """Get a random question on demand"""
        await interaction.response.defer()
        
        question = await self._generate_question()
        
        if question:
            embed = discord.Embed(
                title="🤔 Discussion Question",
                description=question,
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Powered by AI" if self.ai_enabled else "Curated question")
            
            message = await interaction.followup.send(embed=embed)
            
            # Add reaction to encourage participation
            try:
                await message.add_reaction('🤔')
            except discord.Forbidden:
                pass
        else:
            await interaction.followup.send("Sorry, I couldn't generate a question right now. Please try again later!")
    
    @app_commands.command(name="question-config", description="Configure question settings (Admin only)")
    @app_commands.describe(
        channel="Channel for daily questions",
        time="Time for daily questions (HH:MM format, 24-hour)"
    )
    @app_commands.default_permissions(administrator=True)
    async def question_config(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        time: Optional[str] = None
    ):
        """Configure question settings"""
        config_updates = {}
        
        if channel is not None:
            # Check permissions
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "I don't have permission to send messages in that channel!",
                    ephemeral=True
                )
                return
            config_updates['question_channel'] = channel.id
        
        if time is not None:
            # Validate time format
            import re
            time_match = re.match(r'^(\d{1,2}):(\d{2})$', time)
            if not time_match:
                await interaction.response.send_message(
                    "Invalid time format! Use HH:MM (e.g., 09:00 or 15:30)",
                    ephemeral=True
                )
                return
            
            hour, minute = int(time_match.group(1)), int(time_match.group(2))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                await interaction.response.send_message(
                    "Invalid time! Hour must be 0-23 and minute must be 0-59",
                    ephemeral=True
                )
                return
            
            config_updates['question_time'] = time
        
        if not config_updates:
            # Show current configuration
            config = await self.bot.db.get_guild_config(interaction.guild.id)
            embed = discord.Embed(
                title="🤔 Question Configuration",
                color=discord.Color.green()
            )
            
            # Question channel
            question_channel_id = config.get('question_channel')
            if question_channel_id:
                channel_obj = self.bot.get_channel(question_channel_id)
                channel_text = channel_obj.mention if channel_obj else "Deleted Channel"
            else:
                channel_text = "Not configured"
            embed.add_field(name="Question Channel", value=channel_text, inline=True)
            
            # Question time
            question_time = config.get('question_time', '15:00')
            embed.add_field(name="Daily Question Time", value=question_time, inline=True)
            
            # AI status
            ai_status = "✅ Enabled" if self.ai_enabled else "❌ Disabled (no API key)"
            embed.add_field(name="AI Generation", value=ai_status, inline=True)
            
            await interaction.response.send_message(embed=embed)
        else:
            # Update configuration
            await self.bot.db.update_guild_config(interaction.guild.id, **config_updates)
            
            embed = discord.Embed(
                title="✅ Question Configuration Updated",
                color=discord.Color.green()
            )
            
            for key, value in config_updates.items():
                if key == 'question_channel':
                    channel_obj = self.bot.get_channel(value)
                    embed.add_field(name="Question Channel", value=channel_obj.mention if channel_obj else "Unknown", inline=True)
                elif key == 'question_time':
                    embed.add_field(name="Daily Question Time", value=value, inline=True)
            
            if 'question_time' in config_updates:
                embed.set_footer(text="Time changes will take effect within a minute.")
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(QuestionsCog(bot)) 