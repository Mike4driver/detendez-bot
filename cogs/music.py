import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from typing import Optional, Dict, List
import re
from datetime import datetime
import logging
import os
import time

# Check for YouTube cookies file
COOKIES_FILE = 'youtube_cookies.txt'
COOKIES_AVAILABLE = os.path.exists(COOKIES_FILE)

logger = logging.getLogger(__name__)

# YT-DLP options - will be updated with cookies
ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',  
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    # Additional options to avoid bot detection
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    # Skip unavailable fragments
    'fragment_retries': 10,
    'skip_unavailable_fragments': True,
    # Age gate bypass attempts
    'age_limit': 99,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Global ytdl instance - will be updated with cookies
ytdl = None

async def initialize_ytdl():
    """Initialize yt-dlp with cookies"""
    global ytdl, COOKIES_AVAILABLE
    
    # Check if cookies file exists
    COOKIES_AVAILABLE = os.path.exists(COOKIES_FILE)
    
    if COOKIES_AVAILABLE:
        ytdl_format_options['cookiefile'] = COOKIES_FILE
        logger.info(f"YouTube cookies loaded from {COOKIES_FILE}")
    else:
        logger.info("No YouTube cookies file found, using basic yt-dlp")
    
    ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
    return ytdl

async def refresh_ytdl_cookies():
    """Refresh YouTube cookies when needed"""
    global ytdl, COOKIES_AVAILABLE
    
    # Re-check if cookies file exists
    COOKIES_AVAILABLE = os.path.exists(COOKIES_FILE)
    
    if COOKIES_AVAILABLE:
        ytdl_format_options['cookiefile'] = COOKIES_FILE
        ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
        logger.info("YouTube cookies refreshed")
    else:
        logger.warning("No YouTube cookies file found")

class YTDLSource(discord.PCMVolumeTransformer):
    """Audio source for YouTube videos"""
    
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.webpage_url = data.get('webpage_url')
        self.thumbnail = data.get('thumbnail')
    
    @classmethod
    async def create_source(cls, search, *, loop=None, stream=False, retry_with_refresh=True):
        """Create audio source from search query or URL"""
        loop = loop or asyncio.get_event_loop()
        
        # Ensure ytdl is initialized
        if ytdl is None:
            await initialize_ytdl()
        
        try:
            # Extract info
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(search, download=not stream)
            )
            
            if 'entries' in data:
                # Take first item from a playlist
                data = data['entries'][0]
            
            filename = data['url'] if stream else ytdl.prepare_filename(data)
            
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a cookie-related error and we can refresh
            if (('sign in' in error_str or 'bot' in error_str or 'cookies' in error_str) 
                and retry_with_refresh):
                logger.warning("YouTube access error detected...")
                
                # If we don't have cookies, suggest adding them
                if not COOKIES_AVAILABLE:
                    raise Exception(f"YouTube access restricted. Add a {COOKIES_FILE} file for better access.")
                else:
                    # Try refreshing and retry once
                    await refresh_ytdl_cookies()
                    return await cls.create_source(search, loop=loop, stream=stream, retry_with_refresh=False)
            
            # Check for age restriction or other common issues
            if 'age' in error_str or 'restricted' in error_str:
                raise Exception(f"Video is age-restricted or region-blocked: {search}")
            elif 'unavailable' in error_str:
                raise Exception(f"Video is unavailable: {search}")
            elif 'private' in error_str:
                raise Exception(f"Video is private: {search}")
            else:
                raise Exception(f"Error processing audio: {str(e)}")
    
    @classmethod
    async def search_youtube(cls, search, *, loop=None, retry_with_refresh=True):
        """Search YouTube and return video info"""
        loop = loop or asyncio.get_event_loop()
        
        # Ensure ytdl is initialized
        if ytdl is None:
            await initialize_ytdl()
        
        try:
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(f"ytsearch:{search}", download=False)
            )
            
            if 'entries' in data and data['entries']:
                return data['entries'][0]
            return None
        
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if it's a cookie-related error and we can refresh
            if (('sign in' in error_str or 'bot' in error_str or 'cookies' in error_str) 
                and retry_with_refresh):
                logger.warning("YouTube access error detected during search...")
                
                # If we have cookies, try refreshing and retry once
                if COOKIES_AVAILABLE:
                    await refresh_ytdl_cookies()
                    return await cls.search_youtube(search, loop=loop, retry_with_refresh=False)
            
            logger.error(f"YouTube search error: {e}")
            return None

class MusicQueue:
    """Music queue management"""
    
    def __init__(self):
        self.queue: List[Dict] = []
        self.current: Optional[Dict] = None
        self.volume: float = 0.5
    
    def add(self, song_data):
        """Add song to queue"""
        self.queue.append(song_data)
    
    def get_next(self):
        """Get next song from queue"""
        if self.queue:
            return self.queue.pop(0)
        return None
    
    def clear(self):
        """Clear the queue"""
        self.queue.clear()
        self.current = None
    
    def remove(self, index):
        """Remove song at index"""
        if 0 <= index < len(self.queue):
            return self.queue.pop(index)
        return None
    
    def get_queue_display(self):
        """Get formatted queue display"""
        if not self.queue:
            return "Queue is empty"
        
        display = []
        for i, song in enumerate(self.queue[:10]):  # Show first 10
            duration = self.format_duration(song.get('duration', 0))
            display.append(f"{i+1}. **{song['title']}** ({duration})")
        
        if len(self.queue) > 10:
            display.append(f"... and {len(self.queue) - 10} more")
        
        return "\n".join(display)
    
    @staticmethod
    def format_duration(seconds):
        """Format duration in seconds to MM:SS"""
        if not seconds:
            return "Unknown"
        
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

class MusicCog(commands.Cog):
    """Music bot functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.queues: Dict[int, MusicQueue] = {}
        self.inactivity_tasks: Dict[int, asyncio.Task] = {}
        
        # Initialize ytdl on cog load
        asyncio.create_task(self._initialize_ytdl())
    
    async def _initialize_ytdl(self):
        """Initialize ytdl with cookies"""
        await initialize_ytdl()
    
    def get_queue(self, guild_id: int) -> MusicQueue:
        """Get or create queue for guild"""
        if guild_id not in self.queues:
            self.queues[guild_id] = MusicQueue()
        return self.queues[guild_id]
    
    async def join_voice_channel(self, interaction: discord.Interaction):
        """Join user's voice channel"""
        if not interaction.user.voice:
            # Check if interaction was already deferred
            if interaction.response.is_done():
                await interaction.followup.send("You must be in a voice channel!", ephemeral=True)
            else:
                await interaction.response.send_message("You must be in a voice channel!", ephemeral=True)
            return None
        
        channel = interaction.user.voice.channel
        
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.channel != channel:
                await interaction.guild.voice_client.move_to(channel)
        else:
            await channel.connect()
        
        return interaction.guild.voice_client
    
    async def ensure_voice_connection(self, interaction: discord.Interaction):
        """Ensure bot is connected to voice"""
        if not interaction.guild.voice_client:
            return await self.join_voice_channel(interaction)
        return interaction.guild.voice_client
    
    def start_inactivity_timer(self, guild_id: int):
        """Start inactivity timer for auto-disconnect"""
        if guild_id in self.inactivity_tasks:
            self.inactivity_tasks[guild_id].cancel()
        
        self.inactivity_tasks[guild_id] = asyncio.create_task(
            self._inactivity_timeout(guild_id)
        )
    
    async def _inactivity_timeout(self, guild_id: int):
        """Handle inactivity timeout"""
        await asyncio.sleep(300)  # 5 minutes
        
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect()
            self.queues.pop(guild_id, None)
            self.inactivity_tasks.pop(guild_id, None)
    
    def cancel_inactivity_timer(self, guild_id: int):
        """Cancel inactivity timer"""
        if guild_id in self.inactivity_tasks:
            self.inactivity_tasks[guild_id].cancel()
            self.inactivity_tasks.pop(guild_id, None)
    
    async def play_next(self, guild_id: int):
        """Play next song in queue"""
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        
        queue = self.get_queue(guild_id)
        next_song = queue.get_next()
        
        if next_song:
            try:
                source = await YTDLSource.create_source(
                    next_song['webpage_url'], 
                    stream=True
                )
                source.volume = queue.volume
                
                guild.voice_client.play(
                    source, 
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self.play_next(guild_id), 
                        self.bot.loop
                    )
                )
                
                queue.current = next_song
                self.cancel_inactivity_timer(guild_id)
                
            except Exception as e:
                logger.error(f"Error playing song: {e}")
                await self.play_next(guild_id)
        else:
            # No more songs, start inactivity timer
            queue.current = None
            self.start_inactivity_timer(guild_id)
    
    @app_commands.command(name="play", description="Play a song from YouTube")
    @app_commands.describe(query="YouTube URL or search query")
    async def play(self, interaction: discord.Interaction, query: str):
        """Play command"""
        await interaction.response.defer()
        
        # Ensure voice connection
        voice_client = await self.ensure_voice_connection(interaction)
        if not voice_client:
            return
        
        queue = self.get_queue(interaction.guild.id)
        
        try:
            # Search for the song
            if not (query.startswith('http://') or query.startswith('https://')):
                # Search YouTube
                song_data = await YTDLSource.search_youtube(query)
                if not song_data:
                    await interaction.followup.send("❌ No results found! Try a different search term.")
                    return
            else:
                # Direct URL
                loop = asyncio.get_event_loop()
                
                # Ensure ytdl is initialized
                if ytdl is None:
                    await initialize_ytdl()
                
                song_data = await loop.run_in_executor(
                    None, lambda: ytdl.extract_info(query, download=False)
                )
                
                if 'entries' in song_data:
                    song_data = song_data['entries'][0]
            
            # Add to queue
            queue.add(song_data)
            
            embed = discord.Embed(
                title="🎵 Added to Queue",
                description=f"**{song_data['title']}**",
                color=discord.Color.green()
            )
            
            duration = queue.format_duration(song_data.get('duration', 0))
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Position in Queue", value=len(queue.queue), inline=True)
            
            if song_data.get('thumbnail'):
                embed.set_thumbnail(url=song_data['thumbnail'])
            
            await interaction.followup.send(embed=embed)
            
            # Start playing if nothing is currently playing
            if not voice_client.is_playing() and not voice_client.is_paused():
                await self.play_next(interaction.guild.id)
                
        except Exception as e:
            error_message = str(e)
            
            # Provide helpful error messages
            if 'sign in' in error_message.lower() or 'bot' in error_message.lower():
                embed = discord.Embed(
                    title="⚠️ YouTube Access Issue",
                    description="YouTube is blocking requests. This may be due to rate limiting or bot detection.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="What you can do:",
                    value="• Try again in a few minutes\n• Use a different search term\n• Try a direct YouTube URL",
                    inline=False
                )
                
                if not COOKIES_AVAILABLE:
                    embed.add_field(
                        name="Suggestion:",
                        value=f"Add a `{COOKIES_FILE}` file to improve YouTube access",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed)
            
            elif 'age-restricted' in error_message.lower() or 'region-blocked' in error_message.lower():
                await interaction.followup.send("❌ This video is age-restricted or not available in your region.")
            
            elif 'unavailable' in error_message.lower():
                await interaction.followup.send("❌ This video is unavailable or has been removed.")
            
            elif 'private' in error_message.lower():
                await interaction.followup.send("❌ This video is private and cannot be played.")
            
            else:
                await interaction.followup.send(f"❌ Error: {error_message}")
    
    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_command(self, interaction: discord.Interaction):
        """Show queue"""
        queue = self.get_queue(interaction.guild.id)
        
        embed = discord.Embed(
            title="🎵 Music Queue",
            color=discord.Color.blue()
        )
        
        # Current song
        if queue.current:
            duration = queue.format_duration(queue.current.get('duration', 0))
            embed.add_field(
                name="Now Playing",
                value=f"**{queue.current['title']}** ({duration})",
                inline=False
            )
        
        # Queue
        queue_display = queue.get_queue_display()
        embed.add_field(name="Up Next", value=queue_display, inline=False)
        
        embed.add_field(name="Total Songs", value=len(queue.queue), inline=True)
        embed.add_field(name="Volume", value=f"{int(queue.volume * 100)}%", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        """Skip current song"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped!")
    
    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        """Stop music and disconnect"""
        queue = self.get_queue(interaction.guild.id)
        queue.clear()
        
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        
        self.cancel_inactivity_timer(interaction.guild.id)
        await interaction.response.send_message("⏹️ Stopped and disconnected!")
    
    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction):
        """Pause playback"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        
        interaction.guild.voice_client.pause()
        await interaction.response.send_message("⏸️ Paused!")
    
    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction):
        """Resume playback"""
        if not interaction.guild.voice_client or not interaction.guild.voice_client.is_paused():
            await interaction.response.send_message("Nothing is paused!", ephemeral=True)
            return
        
        interaction.guild.voice_client.resume()
        await interaction.response.send_message("▶️ Resumed!")
    
    @app_commands.command(name="volume", description="Set playback volume")
    @app_commands.describe(volume="Volume percentage (0-100)")
    async def volume(self, interaction: discord.Interaction, volume: int):
        """Set volume"""
        if volume < 0 or volume > 100:
            await interaction.response.send_message("Volume must be between 0 and 100!", ephemeral=True)
            return
        
        queue = self.get_queue(interaction.guild.id)
        queue.volume = volume / 100.0
        
        # Update current source volume if playing
        if (interaction.guild.voice_client and 
            interaction.guild.voice_client.source and 
            hasattr(interaction.guild.voice_client.source, 'volume')):
            interaction.guild.voice_client.source.volume = queue.volume
        
        await interaction.response.send_message(f"🔊 Volume set to {volume}%")
    
    @app_commands.command(name="nowplaying", description="Show currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        """Show now playing"""
        queue = self.get_queue(interaction.guild.id)
        
        if not queue.current:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{queue.current['title']}**",
            color=discord.Color.green()
        )
        
        duration = queue.format_duration(queue.current.get('duration', 0))
        embed.add_field(name="Duration", value=duration, inline=True)
        embed.add_field(name="Volume", value=f"{int(queue.volume * 100)}%", inline=True)
        
        if queue.current.get('thumbnail'):
            embed.set_thumbnail(url=queue.current['thumbnail'])
        
        if queue.current.get('webpage_url'):
            embed.add_field(name="URL", value=queue.current['webpage_url'], inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="remove", description="Remove a song from the queue")
    @app_commands.describe(position="Position in queue to remove")
    async def remove(self, interaction: discord.Interaction, position: int):
        """Remove song from queue"""
        queue = self.get_queue(interaction.guild.id)
        
        if position < 1 or position > len(queue.queue):
            await interaction.response.send_message("Invalid queue position!", ephemeral=True)
            return
        
        removed_song = queue.remove(position - 1)
        if removed_song:
            await interaction.response.send_message(f"🗑️ Removed **{removed_song['title']}** from queue")
        else:
            await interaction.response.send_message("Failed to remove song!", ephemeral=True)
    
    @app_commands.command(name="np", description="Alias for nowplaying")
    async def np(self, interaction: discord.Interaction):
        """Alias for nowplaying"""
        await self.nowplaying(interaction)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle voice state updates"""
        # If bot was disconnected, clean up
        if member == self.bot.user and before.channel and not after.channel:
            guild_id = before.channel.guild.id
            self.queues.pop(guild_id, None)
            self.cancel_inactivity_timer(guild_id)
    
    @app_commands.command(name="refresh_cookies", description="Refresh YouTube cookies (Admin only)")
    async def refresh_cookies(self, interaction: discord.Interaction):
        """Refresh YouTube cookies manually"""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            await refresh_ytdl_cookies()
            if COOKIES_AVAILABLE:
                await interaction.followup.send(f"✅ YouTube cookies refreshed from {COOKIES_FILE}!")
            else:
                await interaction.followup.send(f"⚠️ No {COOKIES_FILE} file found. Please add one for better YouTube access.")
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error refreshing cookies: {str(e)}")
    
    @app_commands.command(name="set_cookies", description="Set YouTube cookies for the bot (Admin only)")
    @app_commands.describe(
        cookies="YouTube cookies in Netscape format",
        attachment="Cookie file to upload (optional)"
    )
    async def set_cookies(self, interaction: discord.Interaction, cookies: Optional[str] = None, attachment: Optional[discord.Attachment] = None):
        """Set YouTube cookies for better access"""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            cookies_content = None
            
            # Check if attachment was provided
            if attachment:
                if attachment.size > 1024 * 1024:  # 1MB limit
                    await interaction.followup.send("❌ Cookie file is too large! Maximum size is 1MB.", ephemeral=True)
                    return
                
                # Read the attachment
                cookies_content = (await attachment.read()).decode('utf-8')
                source = "uploaded file"
            
            # Check if cookies text was provided
            elif cookies:
                cookies_content = cookies
                source = "text input"
            
            else:
                embed = discord.Embed(
                    title="🍪 Set YouTube Cookies",
                    description="Provide YouTube cookies to improve bot access to YouTube content.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="How to get cookies:",
                    value="1. Install a browser extension like 'Get cookies.txt'\n2. Visit YouTube while logged in\n3. Export cookies in Netscape format\n4. Provide them via text or file upload",
                    inline=False
                )
                embed.add_field(
                    name="Usage:",
                    value="`/set_cookies cookies:<paste cookies here>`\nor\n`/set_cookies attachment:<upload cookies.txt>`",
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Validate cookies format
            if not self._validate_cookies(cookies_content):
                await interaction.followup.send("❌ Invalid cookie format! Please provide cookies in Netscape format.", ephemeral=True)
                return
            
            # Save cookies to file
            with open(COOKIES_FILE, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            
            # Refresh the ytdl instance
            await refresh_ytdl_cookies()
            
            embed = discord.Embed(
                title="✅ Cookies Set Successfully",
                description=f"YouTube cookies have been saved from {source}.",
                color=discord.Color.green()
            )
            embed.add_field(name="File", value=COOKIES_FILE, inline=True)
            embed.add_field(name="Status", value="Active", inline=True)
            
            # Count cookies
            cookie_lines = [line.strip() for line in cookies_content.split('\n') if line.strip() and not line.startswith('#')]
            embed.add_field(name="Cookies Count", value=len(cookie_lines), inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error setting cookies: {e}")
            await interaction.followup.send(f"❌ Error setting cookies: {str(e)}", ephemeral=True)
    
    def _validate_cookies(self, cookies_content: str) -> bool:
        """Validate cookies are in Netscape format"""
        if not cookies_content or not cookies_content.strip():
            return False
        
        lines = cookies_content.split('\n')
        valid_lines = 0
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
            
            # Netscape format has 7 tab-separated fields
            parts = line.split('\t')
            if len(parts) >= 6:  # Allow for some flexibility
                valid_lines += 1
            elif len(parts) >= 3:  # Minimum viable cookie line
                valid_lines += 1
        
        # Must have at least some valid cookie lines
        return valid_lines > 0
    
    @app_commands.command(name="cookie_status", description="Check cookie status (Admin only)")
    async def cookie_status(self, interaction: discord.Interaction):
        """Check cookie status"""
        # Check if user has admin permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🍪 Cookie Status",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Cookie File", value=f"✅ Found" if COOKIES_AVAILABLE else f"❌ Not Found", inline=False)
        embed.add_field(name="File Path", value=COOKIES_FILE, inline=False)
        
        if COOKIES_AVAILABLE:
            try:
                file_age = int(time.time() - os.path.getmtime(COOKIES_FILE))
                hours = file_age // 3600
                minutes = (file_age % 3600) // 60
                embed.add_field(name="File Age", value=f"{hours}h {minutes}m", inline=True)
                
                # Count cookies in file
                with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                    content = f.read()
                    cookie_lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                    embed.add_field(name="Cookies Count", value=len(cookie_lines), inline=True)
                    
            except Exception as e:
                embed.add_field(name="File Age", value="Unknown", inline=True)
        else:
            embed.add_field(name="Note", value=f"Use `/set_cookies` to add cookies for better YouTube access", inline=False)
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MusicCog(bot)) 