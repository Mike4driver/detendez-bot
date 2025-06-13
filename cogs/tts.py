import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import tempfile
import os
import logging
from typing import Optional, List
from datetime import datetime
from config import Config

try:
    from elevenlabs import Voice, VoiceSettings, generate, set_api_key, voices
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    print("Warning: elevenlabs library not installed; TTS support disabled.")

logger = logging.getLogger(__name__)

class TTSCog(commands.Cog):
    """Text-to-Speech functionality using ElevenLabs API"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tts_enabled = False
        self.available_voices = []
        self.setup_elevenlabs()
    
    def setup_elevenlabs(self):
        """Setup ElevenLabs API"""
        if not ELEVENLABS_AVAILABLE:
            logger.warning("ElevenLabs library not available")
            return
            
        if Config.ELEVENLABS_API_KEY:
            try:
                set_api_key(Config.ELEVENLABS_API_KEY)
                self.tts_enabled = True
                # Get available voices
                asyncio.create_task(self.load_voices())
                logger.info("ElevenLabs TTS initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs: {e}")
                self.tts_enabled = False
        else:
            logger.warning("ELEVENLABS_API_KEY not set")
    
    async def load_voices(self):
        """Load available voices from ElevenLabs"""
        try:
            voice_list = await asyncio.to_thread(voices)
            self.available_voices = [
                {"name": voice.name, "voice_id": voice.voice_id}
                for voice in voice_list
            ]
            logger.info(f"Loaded {len(self.available_voices)} voices from ElevenLabs")
        except Exception as e:
            logger.error(f"Failed to load voices: {e}")
            self.available_voices = []
    
    def get_voice_choices(self) -> List[app_commands.Choice[str]]:
        """Get voice choices for command autocomplete"""
        choices = []
        for voice in self.available_voices[:25]:  # Discord limits to 25 choices
            choices.append(app_commands.Choice(name=voice["name"], value=voice["voice_id"]))
        return choices
    
    @app_commands.command(name="tts", description="Generate text-to-speech audio")
    @app_commands.describe(
        text="Text to convert to speech",
        voice="Voice to use (optional)",
        speed="Speech speed (0.25-4.0, default: 1.0)",
        stability="Voice stability (0.0-1.0, default: 0.5)",
        clarity="Voice clarity (0.0-1.0, default: 0.75)"
    )
    async def tts(
        self, 
        interaction: discord.Interaction, 
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = 1.0,
        stability: Optional[float] = 0.5,
        clarity: Optional[float] = 0.75
    ):
        """Generate text-to-speech audio"""
        await interaction.response.defer()
        
        if not self.tts_enabled:
            await interaction.followup.send(
                "❌ Text-to-speech is disabled. Please configure ELEVENLABS_API_KEY.",
                ephemeral=True
            )
            return
        
        # Validate text length
        if len(text) > Config.MAX_TTS_LENGTH:
            await interaction.followup.send(
                f"❌ Text too long! Maximum {Config.MAX_TTS_LENGTH} characters allowed. "
                f"Your text is {len(text)} characters.",
                ephemeral=True
            )
            return
        
        # Validate parameters
        if not (0.25 <= speed <= 4.0):
            await interaction.followup.send("❌ Speed must be between 0.25 and 4.0", ephemeral=True)
            return
        
        if not (0.0 <= stability <= 1.0):
            await interaction.followup.send("❌ Stability must be between 0.0 and 1.0", ephemeral=True)
            return
        
        if not (0.0 <= clarity <= 1.0):
            await interaction.followup.send("❌ Clarity must be between 0.0 and 1.0", ephemeral=True)
            return
        
        try:
            # Use provided voice or default
            voice_id = voice or Config.DEFAULT_TTS_VOICE
            
            # If voice_id is actually a voice name, find the ID
            if voice_id in [v["name"] for v in self.available_voices]:
                voice_id = next(v["voice_id"] for v in self.available_voices if v["name"] == voice_id)
            
            # Generate audio
            audio = await asyncio.to_thread(
                generate,
                text=text,
                voice=Voice(
                    voice_id=voice_id,
                    settings=VoiceSettings(
                        stability=stability,
                        similarity_boost=clarity,
                        speed=speed
                    )
                )
            )
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio)
                temp_file_path = temp_file.name
            
            # Create embed
            embed = discord.Embed(
                title="🎤 Text-to-Speech Generated",
                description=f"**Text:** {text[:100]}{'...' if len(text) > 100 else ''}",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Voice", value=voice or "Default", inline=True)
            embed.add_field(name="Speed", value=f"{speed}x", inline=True)
            embed.add_field(name="Length", value=f"{len(text)} characters", inline=True)
            embed.set_footer(text=f"Generated by {interaction.user.display_name}")
            
            # Send the audio file
            with open(temp_file_path, 'rb') as f:
                file = discord.File(f, filename="tts_audio.mp3")
                await interaction.followup.send(embed=embed, file=file)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"TTS generation error: {e}")
            await interaction.followup.send(
                f"❌ Error generating speech: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="voices", description="List available TTS voices")
    async def voices_command(self, interaction: discord.Interaction):
        """List available TTS voices"""
        if not self.tts_enabled:
            await interaction.response.send_message(
                "❌ Text-to-speech is disabled. Please configure ELEVENLABS_API_KEY.",
                ephemeral=True
            )
            return
        
        if not self.available_voices:
            await interaction.response.send_message(
                "⏳ Voices are still loading. Please try again in a moment.",
                ephemeral=True
            )
            return
        
        # Create embed with voices
        embed = discord.Embed(
            title="🎙️ Available TTS Voices",
            description="Here are the available voices for text-to-speech:",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Split voices into chunks to avoid embed field limits
        voice_chunks = [self.available_voices[i:i+10] for i in range(0, len(self.available_voices), 10)]
        
        for i, chunk in enumerate(voice_chunks[:5]):  # Limit to 5 fields (50 voices max)
            voice_list = "\n".join([f"• {voice['name']}" for voice in chunk])
            embed.add_field(
                name=f"Voices {i*10+1}-{min((i+1)*10, len(self.available_voices))}",
                value=voice_list,
                inline=True
            )
        
        embed.set_footer(text=f"Total: {len(self.available_voices)} voices available")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="tts-config", description="Configure TTS settings (Admin only)")
    @app_commands.describe(
        max_length="Maximum text length allowed (default: 500)",
        default_voice="Default voice to use"
    )
    @app_commands.default_permissions(administrator=True)
    async def tts_config(
        self, 
        interaction: discord.Interaction,
        max_length: Optional[int] = None,
        default_voice: Optional[str] = None
    ):
        """Configure TTS settings (Admin command)"""
        if not self.tts_enabled:
            await interaction.response.send_message(
                "❌ Text-to-speech is disabled. Please configure ELEVENLABS_API_KEY.",
                ephemeral=True
            )
            return
        
        updates = {}
        
        if max_length is not None:
            if max_length < 1 or max_length > 2000:
                await interaction.response.send_message(
                    "❌ Max length must be between 1 and 2000 characters.",
                    ephemeral=True
                )
                return
            Config.MAX_TTS_LENGTH = max_length
            updates['max_length'] = max_length
        
        if default_voice is not None:
            # Validate voice exists
            voice_names = [v["name"] for v in self.available_voices]
            voice_ids = [v["voice_id"] for v in self.available_voices]
            
            if default_voice not in voice_names and default_voice not in voice_ids:
                await interaction.response.send_message(
                    f"❌ Voice '{default_voice}' not found. Use `/voices` to see available voices.",
                    ephemeral=True
                )
                return
            
            Config.DEFAULT_TTS_VOICE = default_voice
            updates['default_voice'] = default_voice
        
        if not updates:
            await interaction.response.send_message(
                "❌ No valid configuration changes provided.",
                ephemeral=True
            )
            return
        
        # Create response embed
        embed = discord.Embed(
            title="✅ TTS Configuration Updated",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        for key, value in updates.items():
            embed.add_field(name=key.replace('_', ' ').title(), value=str(value), inline=True)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(TTSCog(bot)) 