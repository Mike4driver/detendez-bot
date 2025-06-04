import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time
from typing import Optional
import google.generativeai as genai
from config import Config
import asyncio
import random

class FactsCog(commands.Cog):
    """Fact of the day functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.setup_ai()
        self.daily_fact.start()
    
    def setup_ai(self):
        """Setup Gemini AI"""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False
            print("Warning: Gemini API key not configured. Facts feature disabled.")
    
    def cog_unload(self):
        self.daily_fact.cancel()
    
    @tasks.loop(hours=24)
    async def daily_fact(self):
        """Post daily facts to configured channels"""
        for guild in self.bot.guilds:
            try:
                config = await self.bot.db.get_guild_config(guild.id)
                fact_channel_id = config.get('fact_channel')
                
                if fact_channel_id:
                    channel = self.bot.get_channel(fact_channel_id)
                    if channel:
                        fact = await self._generate_fact()
                        if fact:
                            embed = discord.Embed(
                                title="🧠 Fact of the Day",
                                description=fact,
                                color=discord.Color.blue(),
                                timestamp=datetime.utcnow()
                            )
                            embed.set_footer(text="Daily fact powered by AI")
                            
                            try:
                                await channel.send(embed=embed)
                                
                                # Store in recent content to avoid repetition
                                await self._store_recent_content(guild.id, fact)
                                
                            except discord.Forbidden:
                                pass
            
            except Exception as e:
                print(f"Error posting daily fact for guild {guild.id}: {e}")
    
    @daily_fact.before_loop
    async def before_daily_fact(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
        
        # Wait until it's the right time (if configured)
        now = datetime.now()
        target_time = time(9, 0)  # 9 AM default
        
        # Calculate seconds until target time
        target_datetime = datetime.combine(now.date(), target_time)
        if target_datetime <= now:
            target_datetime = datetime.combine(now.date().replace(day=now.day + 1), target_time)
        
        wait_seconds = (target_datetime - now).total_seconds()
        await asyncio.sleep(wait_seconds)
    
    async def _generate_fact(self) -> Optional[str]:
        """Generate a fun fact using AI"""
        if not self.ai_enabled:
            return self._get_fallback_fact()
        
        try:
            prompts = [
                "Generate a fascinating and surprising fact about science, history, nature, or space. Make it interesting and educational, suitable for all ages. Keep it under 300 characters.",
                "Share an amazing fact about animals, geography, technology, or human behavior. Make it engaging and fun to read. Keep it concise (under 300 characters).",
                "Tell me an incredible fact about the universe, ancient civilizations, or natural phenomena. Make it mind-blowing but easy to understand. Keep it brief (under 300 characters).",
                "Give me a cool fact about inventions, discoveries, or cultural traditions from around the world. Make it interesting and appropriate for everyone. Keep it short (under 300 characters)."
            ]
            
            prompt = random.choice(prompts)
            
            # Check for recent facts to avoid repetition
            recent_facts = await self._get_recent_facts()
            if recent_facts:
                prompt += f"\n\nAvoid these recently posted facts: {'; '.join(recent_facts[:5])}"
            
            response = await asyncio.to_thread(
                self.model.generate_content, prompt
            )
            
            fact = response.text.strip()
            
            # Basic validation
            if len(fact) > 400:
                fact = fact[:397] + "..."
            
            return fact
            
        except Exception as e:
            print(f"Error generating fact: {e}")
            return self._get_fallback_fact()
    
    def _get_fallback_fact(self) -> str:
        """Get a fallback fact when AI is unavailable"""
        facts = [
            "Honey never spoils! Archaeologists have found pots of honey in ancient Egyptian tombs that are over 3,000 years old and still perfectly edible.",
            "A single cloud can weigh more than a million pounds! Despite appearing light and fluffy, clouds contain massive amounts of water droplets.",
            "Octopuses have three hearts and blue blood! Two hearts pump blood to the gills, while the third pumps blood to the rest of the body.",
            "Bananas are berries, but strawberries aren't! Botanically speaking, berries must have seeds inside their flesh.",
            "A group of flamingos is called a 'flamboyance'! These pink birds are also born gray and turn pink from their diet.",
            "The shortest war in history lasted only 38-45 minutes! It was between Britain and Zanzibar in 1896.",
            "Wombat poop is cube-shaped! This unique shape helps prevent it from rolling away and marks their territory.",
            "A shrimp's heart is located in its head! Their anatomy is quite different from most other animals."
        ]
        return random.choice(facts)
    
    async def _store_recent_content(self, guild_id: int, content: str):
        """Store recently posted content to avoid repetition"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO recent_content (guild_id, content_type, content, posted_date)
                VALUES (?, 'fact', ?, DATE('now'))
            ''', (guild_id, content))
            
            # Clean up old content (keep only last 30 days)
            await db.execute('''
                DELETE FROM recent_content 
                WHERE content_type = 'fact' 
                AND guild_id = ? 
                AND posted_date < DATE('now', '-30 days')
            ''', (guild_id,))
            
            await db.commit()
    
    async def _get_recent_facts(self) -> list:
        """Get recently posted facts to avoid repetition"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute('''
                SELECT content FROM recent_content 
                WHERE content_type = 'fact' 
                AND posted_date > DATE('now', '-7 days')
                ORDER BY posted_date DESC
                LIMIT 10
            ''') as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    @app_commands.command(name="fact", description="Get a random fun fact")
    async def fact_command(self, interaction: discord.Interaction):
        """Get a random fact on demand"""
        await interaction.response.defer()
        
        fact = await self._generate_fact()
        
        if fact:
            embed = discord.Embed(
                title="🧠 Fun Fact",
                description=fact,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Powered by AI" if self.ai_enabled else "Curated fact")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("Sorry, I couldn't generate a fact right now. Please try again later!")
    
    @app_commands.command(name="fact-config", description="Configure fact settings (Admin only)")
    @app_commands.describe(
        channel="Channel for daily facts",
        time="Time for daily facts (HH:MM format, 24-hour)"
    )
    @app_commands.default_permissions(administrator=True)
    async def fact_config(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        time: Optional[str] = None
    ):
        """Configure fact settings"""
        config_updates = {}
        
        if channel is not None:
            # Check permissions
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "I don't have permission to send messages in that channel!",
                    ephemeral=True
                )
                return
            config_updates['fact_channel'] = channel.id
        
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
            
            config_updates['fact_time'] = time
        
        if not config_updates:
            # Show current configuration
            config = await self.bot.db.get_guild_config(interaction.guild.id)
            embed = discord.Embed(
                title="🧠 Fact Configuration",
                color=discord.Color.blue()
            )
            
            # Fact channel
            fact_channel_id = config.get('fact_channel')
            if fact_channel_id:
                channel_obj = self.bot.get_channel(fact_channel_id)
                channel_text = channel_obj.mention if channel_obj else "Deleted Channel"
            else:
                channel_text = "Not configured"
            embed.add_field(name="Fact Channel", value=channel_text, inline=True)
            
            # Fact time
            fact_time = config.get('fact_time', '09:00')
            embed.add_field(name="Daily Fact Time", value=fact_time, inline=True)
            
            # AI status
            ai_status = "✅ Enabled" if self.ai_enabled else "❌ Disabled (no API key)"
            embed.add_field(name="AI Generation", value=ai_status, inline=True)
            
            await interaction.response.send_message(embed=embed)
        else:
            # Update configuration
            await self.bot.db.update_guild_config(interaction.guild.id, **config_updates)
            
            embed = discord.Embed(
                title="✅ Fact Configuration Updated",
                color=discord.Color.green()
            )
            
            for key, value in config_updates.items():
                if key == 'fact_channel':
                    channel_obj = self.bot.get_channel(value)
                    embed.add_field(name="Fact Channel", value=channel_obj.mention if channel_obj else "Unknown", inline=True)
                elif key == 'fact_time':
                    embed.add_field(name="Daily Fact Time", value=value, inline=True)
            
            # Note about restart requirement for time changes
            if 'fact_time' in config_updates:
                embed.add_field(
                    name="⚠️ Note", 
                    value="Time changes will take effect after bot restart", 
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FactsCog(bot)) 