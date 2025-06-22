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
    from elevenlabs.client import ElevenLabs
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
        self.elevenlabs_client = None
        self.setup_elevenlabs()
    
    def setup_elevenlabs(self):
        """Setup ElevenLabs API"""
        if not ELEVENLABS_AVAILABLE:
            logger.warning("ElevenLabs library not available")
            return
            
        if Config.ELEVENLABS_API_KEY:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=Config.ELEVENLABS_API_KEY)
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
        if not self.elevenlabs_client:
            return
            
        try:
            response = await asyncio.to_thread(self.elevenlabs_client.voices.search)
            self.available_voices = [
                {"name": voice.name, "voice_id": voice.voice_id}
                for voice in response.voices
            ]
            logger.info(f"Loaded {len(self.available_voices)} voices from ElevenLabs")
        except Exception as e:
            logger.error(f"Failed to load voices: {e}")
            self.available_voices = []

    @app_commands.command(name="tts", description="Generate text-to-speech audio")
    @app_commands.describe(
        text="Text to convert to speech",
        voice="Voice ID or name to use (optional)",
        model="Model to use (optional)"
    )
    async def tts(
        self, 
        interaction: discord.Interaction, 
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Generate text-to-speech audio"""
        await interaction.response.defer()
        
        if not self.tts_enabled or not self.elevenlabs_client:
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
        
        # Validate model
        valid_models = [
            "eleven_multilingual_v2",
            "eleven_flash_v2_5", 
            "eleven_turbo_v2_5"
        ]
        model_id = model or Config.DEFAULT_TTS_MODEL
        if model_id not in valid_models:
            await interaction.followup.send(
                f"❌ Invalid model. Valid options: {', '.join(valid_models)}",
                ephemeral=True
            )
            return
        
        try:
            # Use provided voice or default
            voice_id = voice or Config.DEFAULT_TTS_VOICE
            
            # If voice_id is actually a voice name, find the ID
            if voice_id in [v["name"] for v in self.available_voices]:
                voice_id = next(v["voice_id"] for v in self.available_voices if v["name"] == voice_id)
            
            # Generate audio using the ElevenLabs API
            audio = await asyncio.to_thread(
                self.elevenlabs_client.text_to_speech.convert,
                text=text,
                voice_id=voice_id,
                model_id=model_id,
                output_format="mp3_44100_128"
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
            
            # Find voice name for display
            voice_name = voice or "Default"
            if voice_id in [v["voice_id"] for v in self.available_voices]:
                voice_name = next(v["name"] for v in self.available_voices if v["voice_id"] == voice_id)
            
            embed.add_field(name="Voice", value=voice_name, inline=True)
            embed.add_field(name="Model", value=model_id, inline=True)
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
        if not self.tts_enabled or not self.elevenlabs_client:
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
        voice_chunks = [self.available_voices[i:i+8] for i in range(0, len(self.available_voices), 8)]
        
        for i, chunk in enumerate(voice_chunks[:6]):  # Limit to 6 fields (48 voices max)
            voice_list = "\n".join([f"• **{voice['name']}**\n  `{voice['voice_id']}`" for voice in chunk])
            embed.add_field(
                name=f"Voices {i*8+1}-{min((i+1)*8, len(self.available_voices))}",
                value=voice_list,
                inline=True
            )
        
        embed.set_footer(text=f"Total: {len(self.available_voices)} voices available")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="tts-models", description="List available TTS models")
    async def models_command(self, interaction: discord.Interaction):
        """List available TTS models"""
        if not self.tts_enabled or not self.elevenlabs_client:
            await interaction.response.send_message(
                "❌ Text-to-speech is disabled. Please configure ELEVENLABS_API_KEY.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🤖 Available TTS Models",
            description="Here are the available models for text-to-speech:",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="eleven_multilingual_v2",
            value="• Excels in stability, language diversity, and accent accuracy\n• Supports 29 languages\n• Recommended for most use cases",
            inline=False
        )
        
        embed.add_field(
            name="eleven_flash_v2_5",
            value="• Ultra-low latency\n• Supports 32 languages\n• Faster model, 50% lower price per character",
            inline=False
        )
        
        embed.add_field(
            name="eleven_turbo_v2_5",
            value="• Good balance of quality and latency\n• Ideal for developer use cases where speed is crucial\n• Supports 32 languages",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tts-stream", description="Generate streaming text-to-speech audio")
    @app_commands.describe(
        text="Text to convert to speech (streaming)",
        voice="Voice ID or name to use (optional)",
        model="Model to use (optional)"
    )
    async def tts_stream(
        self, 
        interaction: discord.Interaction, 
        text: str,
        voice: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Generate streaming text-to-speech audio"""
        await interaction.response.defer()
        
        if not self.tts_enabled or not self.elevenlabs_client:
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
        
        # Validate model
        valid_models = [
            "eleven_multilingual_v2",
            "eleven_flash_v2_5", 
            "eleven_turbo_v2_5"
        ]
        model_id = model or Config.DEFAULT_TTS_MODEL
        if model_id not in valid_models:
            await interaction.followup.send(
                f"❌ Invalid model. Valid options: {', '.join(valid_models)}",
                ephemeral=True
            )
            return
        
        try:
            # Use provided voice or default
            voice_id = voice or Config.DEFAULT_TTS_VOICE
            
            # If voice_id is actually a voice name, find the ID
            if voice_id in [v["name"] for v in self.available_voices]:
                voice_id = next(v["voice_id"] for v in self.available_voices if v["name"] == voice_id)
            
            # Generate streaming audio
            audio_stream = await asyncio.to_thread(
                self.elevenlabs_client.text_to_speech.stream,
                text=text,
                voice_id=voice_id,
                model_id=model_id
            )
            
            # Collect all audio chunks
            audio_data = b""
            for chunk in audio_stream:
                if isinstance(chunk, bytes):
                    audio_data += chunk
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file_path = temp_file.name
            
            # Create embed
            embed = discord.Embed(
                title="🎤 Streaming TTS Generated",
                description=f"**Text:** {text[:100]}{'...' if len(text) > 100 else ''}",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            
            # Find voice name for display
            voice_name = voice or "Default"
            if voice_id in [v["voice_id"] for v in self.available_voices]:
                voice_name = next(v["name"] for v in self.available_voices if v["voice_id"] == voice_id)
            
            embed.add_field(name="Voice", value=voice_name, inline=True)
            embed.add_field(name="Model", value=model_id, inline=True)
            embed.add_field(name="Type", value="Streaming", inline=True)
            embed.set_footer(text=f"Generated by {interaction.user.display_name}")
            
            # Send the audio file
            with open(temp_file_path, 'rb') as f:
                file = discord.File(f, filename="tts_stream_audio.mp3")
                await interaction.followup.send(embed=embed, file=file)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
        except Exception as e:
            logger.error(f"TTS streaming error: {e}")
            await interaction.followup.send(
                f"❌ Error generating streaming speech: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="tts-config", description="Configure TTS settings (Admin only)")
    @app_commands.describe(
        max_length="Maximum text length allowed (1-2000)",
        default_voice="Default voice ID or name to use",
        default_model="Default model to use"
    )
    @app_commands.default_permissions(administrator=True)
    async def tts_config(
        self, 
        interaction: discord.Interaction,
        max_length: Optional[int] = None,
        default_voice: Optional[str] = None,
        default_model: Optional[str] = None
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
        
        if default_model is not None:
            valid_models = [
                "eleven_multilingual_v2",
                "eleven_flash_v2_5", 
                "eleven_turbo_v2_5"
            ]
            if default_model not in valid_models:
                await interaction.response.send_message(
                    f"❌ Invalid model. Valid options: {', '.join(valid_models)}",
                    ephemeral=True
                )
                return
            
            Config.DEFAULT_TTS_MODEL = default_model
            updates['default_model'] = default_model
        
        if not updates:
            # Show current configuration
            embed = discord.Embed(
                title="⚙️ Current TTS Configuration",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Max Length", value=f"{Config.MAX_TTS_LENGTH} characters", inline=True)
            embed.add_field(name="Default Voice", value=Config.DEFAULT_TTS_VOICE, inline=True)
            embed.add_field(name="Default Model", value=Config.DEFAULT_TTS_MODEL, inline=True)
            embed.add_field(name="Available Voices", value=len(self.available_voices), inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
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