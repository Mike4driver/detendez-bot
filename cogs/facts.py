import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time, timezone
from typing import Optional
import google.generativeai as genai
from config import Config
import asyncio
import random
import logging

logger = logging.getLogger(__name__)

class RegenerateFactView(discord.ui.View):
    """View with a regenerate button for facts"""
    
    def __init__(self, cog, guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
    
    @discord.ui.button(label="Regenerate Fact", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def regenerate_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user is admin or has admin role
        config = await self.cog.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config.get('admin_role') if config else None
        is_admin = interaction.user.guild_permissions.administrator
        has_admin_role = admin_role_id and interaction.guild.get_role(admin_role_id) in interaction.user.roles
        
        if not (is_admin or has_admin_role):
            await interaction.response.send_message(
                "❌ Only administrators can regenerate facts!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Generate new fact
        new_fact = await self.cog._generate_fact()
        
        if new_fact:
            embed = discord.Embed(
                title="🧠 Fact of the Day",
                description=new_fact,
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text="Daily fact powered by Beanz! • Regenerated")
            
            # Update the message
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send("✅ Fact regenerated!", ephemeral=True)
            
            # Store the new fact
            await self.cog._store_recent_content(self.guild_id, new_fact)
        else:
            await interaction.followup.send("❌ Failed to generate a new fact. Try again.", ephemeral=True)

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
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False
            print("Warning: Gemini API key not configured. Facts feature disabled.")
    
    def cog_unload(self):
        self.daily_fact.cancel()
    
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
    async def daily_fact(self):
        """Post daily facts to configured channels at the configured time."""
        now = datetime.now()
        current_time = time(now.hour, now.minute)

        for guild in self.bot.guilds:
            try:
                config = await self.bot.db.get_guild_config(guild.id)
                fact_channel_id = config.get('fact_channel')
                
                if not fact_channel_id:
                    continue

                fact_time_str = config.get('fact_time', '09:00')

                try:
                    hour, minute = map(int, fact_time_str.split(':'))
                    target_time = time(hour, minute)
                except (ValueError, AttributeError):
                    target_time = time(9, 0)
                
                if current_time == target_time:
                    if not await self._has_posted_today(guild.id, 'fact'):
                        channel = self.bot.get_channel(fact_channel_id)
                        if channel:
                            fact = await self._generate_fact()
                            if fact:
                                embed = discord.Embed(
                                    title="🧠 Fact of the Day",
                                    description=fact,
                                    color=discord.Color.blue(),
                                    timestamp=datetime.now(timezone.utc)
                                )
                                embed.set_footer(text="Daily fact powered by Beanz!")
                                
                                # Create view with regenerate button
                                view = RegenerateFactView(self, guild.id)
                                
                                try:
                                    await channel.send(embed=embed, view=view)
                                    await self._store_recent_content(guild.id, fact)
                                except discord.Forbidden:
                                    logger.warning(f"No permission in channel {fact_channel_id} for guild {guild.id}")

            except Exception as e:
                logger.error(f"Error in daily_fact loop for guild {guild.id}: {e}")
    
    @daily_fact.before_loop
    async def before_daily_fact(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
    
    async def _generate_fact(self) -> Optional[str]:
        """Generate a fun fact using AI"""
        if not self.ai_enabled:
            return self._get_fallback_fact()
        
        try:
            prompts = [
                "Share a counter-intuitive fact that challenges a common assumption. The fact should make people say 'wait, really?' and question what they thought they knew. Avoid well-known facts like 'honey never spoils' or 'octopuses have three hearts'. Focus on something obscure but verifiable.",
                "Reveal a fact about etymology or word origins that explains something unexpected about language. Choose a word with a surprising history that reveals hidden connections or cultural shifts. Make it specific and fascinating.",
                "Tell me about a failed invention or discovery that was ahead of its time or failed for an interesting reason. Focus on something obscure but significant. Explain why it didn't catch on in a way that reveals something about history or human nature.",
                "Share a fact about animal behavior that seems bizarre or counterintuitive. Choose something specific about a particular species that challenges assumptions about how animals work. Avoid common examples like 'dolphins are smart'.",
                "Reveal a historical misconception - something people commonly believe about history that's actually wrong. Make it specific and surprising. Help correct a widespread misunderstanding with an interesting backstory.",
                "Tell me about an accidental discovery that changed the world. Focus on something lesser-known but impactful. Explain the serendipitous circumstances in a way that makes the discovery feel inevitable yet surprising.",
                "Share a fact about the human body that seems impossible but is true. Choose something specific and counterintuitive about anatomy, physiology, or psychology. Make it something that makes people check their own bodies.",
                "Reveal a fact about a weird law, regulation, or legal oddity from history or around the world. Make it specific and explain the context that made it seem reasonable at the time. Avoid overly common examples.",
                "Tell me about a linguistic oddity - something strange about how language works, untranslatable words, or language quirks. Make it specific and reveal how language shapes thought in unexpected ways.",
                "Share a fact about scale comparisons that puts things in perspective in a mind-blowing way. Compare sizes, times, distances, or quantities in ways that reveal hidden truths. Make it specific and visual.",
                "Reveal a fact about a natural phenomenon that seems magical but has a scientific explanation. Choose something specific and lesser-known. Make the explanation as fascinating as the phenomenon itself.",
                "Tell me about an obscure historical event or figure that had massive consequences but is rarely discussed. Make it specific and explain the ripple effects. Help people see how history turns on forgotten details.",
                "Share a fact about food, cooking, or culinary history that reveals something unexpected about culture, science, or human behavior. Make it specific and avoid common food facts. Focus on something that makes people reconsider what they eat.",
                "Reveal a fact about technology or engineering that seems impossible but is true. Choose something specific about how something works that challenges assumptions. Make it accessible but mind-blowing.",
                "Tell me about a paradox or logical puzzle that exists in the real world (not just theoretical). Explain a situation where reality seems to contradict itself. Make it specific and verifiable.",
                "Share a fact about space, astronomy, or the universe that puts human existence in perspective. Choose something specific and mind-boggling about scale, time, or cosmic phenomena. Make it humbling and awe-inspiring.",
                "Reveal a fact about a cultural practice, tradition, or custom from a specific place/time that seems strange but makes perfect sense in context. Make it specific and help people understand different worldviews.",
                "Tell me about a 'butterfly effect' moment - a small, seemingly insignificant event that had massive historical consequences. Make it specific and trace the unexpected connections. Show how tiny details change everything.",
                "Share a fact about mathematics or patterns in nature that reveals hidden beauty or order. Choose something specific and visual that makes abstract concepts tangible. Make it surprising and elegant.",
                "Reveal a fact about psychology or human behavior that explains something we all experience but rarely think about. Make it specific and help people understand themselves better. Avoid generic psychology facts.",
                "Tell me about an edge case or exception to a general rule in science, nature, or human behavior. Find something that 'breaks' common assumptions. Make it specific and reveal how reality is more complex than we think.",
                "Share a fact about the ocean, marine life, or underwater phenomena that seems impossible. Choose something specific and lesser-known. Make it reveal how much we still don't know about the deep sea.",
                "Reveal a fact about time, perception, or how we experience reality that challenges assumptions. Make it specific and make people question their own experience of time or consciousness.",
                "Tell me about a fact that connects seemingly unrelated things in an unexpected way. Reveal hidden connections between history, science, culture, or nature. Make it specific and surprising.",
                "Share a fact about a 'what could have been' moment - an invention, discovery, or historical path that almost happened but didn't. Make it specific and explain the alternate timeline that almost was.",
                "Reveal a fact about survival, adaptation, or evolution that seems impossible but is true. Choose something specific about how life finds a way in extreme circumstances. Make it awe-inspiring and specific.",
                "Tell me about a fact that reveals something hidden in plain sight - something we see every day but don't understand. Make it specific and make people look at the world differently. Focus on something mundane made fascinating."
            ]
            
            prompt = random.choice(prompts)
            
            # Check for recent facts to avoid repetition
            recent_facts = await self._get_recent_facts()
            if recent_facts:
                prompt += f"\n\nAvoid these recently posted facts: {'; '.join(recent_facts)}"
            
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
        logger.info(f"Storing recent content for guild {guild_id}: {content}")
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO recent_content (guild_id, content_type, content, posted_date)
                VALUES (?, 'fact', ?, DATE('now'))
            ''', (guild_id, content))
            
            # Clean up old content (keep only last 30 days)
            # await db.execute('''
            #     DELETE FROM recent_content 
            #     WHERE content_type = 'fact' 
            #     AND guild_id = ? 
            #     AND posted_date < DATE('now', '-30 days')
            # ''', (guild_id,))
            
            await db.commit()
    
    async def _get_recent_facts(self) -> list:
        """Get recently posted facts to avoid repetition"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute('''
                SELECT content FROM recent_content 
                WHERE content_type = 'fact' 
                AND posted_date > DATE('now', '-60 days')
                ORDER BY posted_date DESC
                LIMIT 50
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
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_footer(text="Powered by Beanz!" if self.ai_enabled else "Curated fact")
            
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
        # Elevate if user has configured admin role
        config_all = await self.bot.db.get_guild_config(interaction.guild.id)
        admin_role_id = config_all.get('admin_role') if config_all else None
        if not interaction.user.guild_permissions.administrator:
            if not admin_role_id or (interaction.guild.get_role(admin_role_id) not in interaction.user.roles):
                await interaction.response.send_message("❌ You need Administrator or the configured Admin Role to use this command!", ephemeral=True)
                return

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
            
            if 'fact_time' in config_updates:
                embed.set_footer(text="Time changes will take effect within a minute.")
            
            await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(FactsCog(bot)) 