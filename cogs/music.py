import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import yt_dlp
from typing import Optional, Dict, List
import logging
import os
import time

logger = logging.getLogger(__name__)

COOKIES_FILE = "youtube_cookies.txt"

YTDL_OPTS_BASE: Dict[str, object] = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
}

FFMPEG_OPTS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


def build_ytdl() -> yt_dlp.YoutubeDL:
    opts = dict(YTDL_OPTS_BASE)
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
        logger.info("Using YouTube cookies file")
    return yt_dlp.YoutubeDL(opts)


class GuildMusicState:
    def __init__(self) -> None:
        self.queue: List[Dict] = []
        self.current: Optional[Dict] = None
        self.volume: float = 0.5
        self.announce_channel_id: Optional[int] = None
        self.last_voice_channel_id: Optional[int] = None

    def enqueue(self, item: Dict) -> None:
        self.queue.append(item)

    def next(self) -> Optional[Dict]:
        if not self.queue:
            return None
        return self.queue.pop(0)

    def clear(self) -> None:
        self.queue.clear()
        self.current = None

    @staticmethod
    def fmt_duration(seconds: Optional[int]) -> str:
        if not seconds:
            return "Unknown"
        minutes = int(seconds // 60)
        sec = int(seconds % 60)
        return f"{minutes}:{sec:02d}"


class MusicCog(commands.Cog):
    """Reliable YouTube playback with queue management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.states: Dict[int, GuildMusicState] = {}
        self._ytdl = build_ytdl()
        self._inactivity_tasks: Dict[int, asyncio.Task] = {}
        self._voice_locks: Dict[int, asyncio.Lock] = {}

    def state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState()
        return self.states[guild_id]

    async def ensure_connected(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user or not getattr(interaction.user, "voice", None) or not interaction.user.voice:
            await interaction.response.send_message("You must be in a voice channel!", ephemeral=True)
            return None
        channel = interaction.user.voice.channel
        gid = interaction.guild.id
        try:
            shard = interaction.guild.shard_id
        except Exception:
            shard = None
        try:
            bot_id = self.bot.user.id if self.bot.user else None
        except Exception:
            bot_id = None
        logger.info(f"[voice] connect request guild={gid} shard={shard} channel={channel.id} bot_id={bot_id}")
        lock = self._voice_locks.setdefault(gid, asyncio.Lock())
        async with lock:
            vc = interaction.guild.voice_client
            # If connected to different channel, try moving; otherwise connect with retries
            for attempt in range(3):
                try:
                    if vc and vc.channel != channel:
                        await vc.move_to(channel)
                    elif not vc:
                        logger.info(f"[voice] connecting... attempt={attempt+1}")
                        vc = await channel.connect(timeout=20.0, reconnect=True, self_deaf=True)
                    # Wait until handshake completes
                    ok = await self._wait_voice_ready(vc, timeout=12.0)
                    if ok:
                        # Remember last voice channel for re-connects
                        self.state(gid).last_voice_channel_id = channel.id
                        logger.info(f"[voice] connected guild={gid} channel={channel.id}")
                        return vc
                    # If not ok, force disconnect and retry
                    try:
                        await vc.disconnect(force=True)
                    except Exception:
                        pass
                    vc = None
                except Exception:
                    # Backoff a bit before retry
                    await asyncio.sleep(2 + attempt * 2)
            # Final failure
            await interaction.followup.send("❌ Failed to join voice channel. Please try again.", ephemeral=True)
            return None

    async def _wait_voice_ready(self, vc: Optional[discord.VoiceClient], *, timeout: float = 8.0) -> bool:
        if not vc:
            return False
        # Poll is_connected; discord.py voice client sets this after handshake
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while loop.time() < end:
            # When fully ready, voice WS and UDP are set up
            if getattr(vc, "is_connected", lambda: False)() and getattr(vc, "channel", None) is not None:
                return True
            await asyncio.sleep(0.2)
        return False

    def _schedule_inactivity(self, guild_id: int) -> None:
        if guild_id in self._inactivity_tasks:
            self._inactivity_tasks[guild_id].cancel()
        self._inactivity_tasks[guild_id] = asyncio.create_task(self._inactivity_timeout(guild_id))

    async def _inactivity_timeout(self, guild_id: int) -> None:
        await asyncio.sleep(300)
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect()
        self.states.pop(guild_id, None)
        self._inactivity_tasks.pop(guild_id, None)

    async def _extract_info(self, query: str, *, search: bool) -> Optional[Dict]:
        def _work():
            if search:
                data = self._ytdl.extract_info(f"ytsearch1:{query}", download=False)
                if data and data.get("entries"):
                    return data["entries"][0]
                return None
            else:
                data = self._ytdl.extract_info(query, download=False)
                if data and data.get("entries"):
                    return data["entries"][0]
                return data

        loop = asyncio.get_running_loop()
        try:
            info = await loop.run_in_executor(None, _work)
            return info
        except Exception as e:
            logger.error(f"yt-dlp error: {e}")
            return None

    async def _play_next(self, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return
        st = self.state(guild_id)
        # Ensure voice connection exists before attempting to play
        if not guild.voice_client or not getattr(guild.voice_client, "is_connected", lambda: False)():
            # Try to reconnect to last known channel
            if st.last_voice_channel_id:
                channel = guild.get_channel(st.last_voice_channel_id)
                if isinstance(channel, discord.VoiceChannel):
                    try:
                        vc = await channel.connect(timeout=10.0, reconnect=True)
                        ok = await self._wait_voice_ready(vc, timeout=8.0)
                        if not ok:
                            try:
                                await vc.disconnect(force=True)
                            except Exception:
                                pass
                            return
                    except Exception:
                        return
            else:
                return
        next_item = st.next()
        if not next_item:
            st.current = None
            self._schedule_inactivity(guild_id)
            return

        st.current = next_item
        url = next_item.get("url")
        if not url:
            info = await self._extract_info(next_item.get("webpage_url", ""), search=False)
            if not info:
                await self._play_next(guild_id)
                return
            url = info.get("url")

        source = discord.FFmpegPCMAudio(url, **FFMPEG_OPTS)
        pcm = discord.PCMVolumeTransformer(source, volume=st.volume)

        def _after(_: Optional[BaseException]) -> None:
            asyncio.run_coroutine_threadsafe(self._play_next(guild_id), self.bot.loop)

        guild.voice_client.play(pcm, after=_after)

        # Announce now playing in the configured channel
        await self._announce_now_playing(guild_id)

    def _build_now_playing_embed(self, st: GuildMusicState) -> discord.Embed:
        title = st.current.get('title', 'Unknown') if st.current else 'Unknown'
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**{title}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Volume", value=f"{int(st.volume*100)}%", inline=True)
        url = st.current.get("webpage_url") if st.current else None
        if url:
            embed.add_field(name="URL", value=url, inline=False)
        thumb = st.current.get("thumbnail") if st.current else None
        if thumb:
            embed.set_thumbnail(url=thumb)
        return embed

    async def _announce_now_playing(self, guild_id: int) -> None:
        st = self.state(guild_id)
        if not st.current or not st.announce_channel_id:
            return
        channel = self.bot.get_channel(st.announce_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            embed = self._build_now_playing_embed(st)
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="play", description="Play a song from YouTube (URL or search query)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        vc = await self.ensure_connected(interaction)
        if not vc:
            return

        # Remember channel for now playing announcements
        st = self.state(interaction.guild.id)
        st.announce_channel_id = interaction.channel.id if interaction.channel else None

        is_url = query.startswith("http://") or query.startswith("https://")
        info = await self._extract_info(query, search=not is_url)
        if not info:
            await interaction.followup.send("❌ No results found or unable to extract audio.")
            return

        item = {
            "title": info.get("title", "Unknown title"),
            "url": info.get("url"),
            "webpage_url": info.get("webpage_url", query if is_url else info.get("original_url", "")),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
        }

        st.enqueue(item)

        embed = discord.Embed(title="🎵 Added to Queue", description=f"**{item['title']}**", color=discord.Color.green())
        embed.add_field(name="Position", value=str(len(st.queue)), inline=True)
        embed.add_field(name="Duration", value=st.fmt_duration(item.get("duration")), inline=True)
        thumb = item.get("thumbnail")
        if thumb:
            embed.set_thumbnail(url=thumb)
        await interaction.followup.send(embed=embed)

        if not vc.is_playing() and not vc.is_paused():
            await self._play_next(interaction.guild.id)

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped!")

    @app_commands.command(name="stop", description="Stop music and clear queue")
    async def stop(self, interaction: discord.Interaction):
        st = self.state(interaction.guild.id)
        st.clear()
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("⏹️ Stopped and disconnected!")

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        vc.pause()
        await interaction.response.send_message("⏸️ Paused!")

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_paused():
            await interaction.response.send_message("Nothing is paused!", ephemeral=True)
            return
        vc.resume()
        await interaction.response.send_message("▶️ Resumed!")

    @app_commands.command(name="volume", description="Set playback volume (0-100)")
    async def volume(self, interaction: discord.Interaction, volume: int):
        if volume < 0 or volume > 100:
            await interaction.response.send_message("Volume must be between 0 and 100!", ephemeral=True)
            return
        st = self.state(interaction.guild.id)
        st.volume = volume / 100.0
        vc = interaction.guild.voice_client
        if vc and vc.source and hasattr(vc.source, "volume"):
            vc.source.volume = st.volume
        await interaction.response.send_message(f"🔊 Volume set to {volume}%")

    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        st = self.state(interaction.guild.id)
        embed = discord.Embed(title="🎵 Music Queue", color=discord.Color.blue())
        if st.current:
            embed.add_field(name="Now Playing", value=f"**{st.current.get('title','Unknown')}**", inline=False)
        if st.queue:
            lines = []
            for idx, it in enumerate(st.queue[:10], 1):
                lines.append(f"{idx}. {it.get('title','Unknown')} ({st.fmt_duration(it.get('duration'))})")
            if len(st.queue) > 10:
                lines.append(f"... and {len(st.queue) - 10} more")
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Up Next", value="Queue is empty", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="remove", description="Remove a song from the queue by position")
    async def remove(self, interaction: discord.Interaction, position: int):
        st = self.state(interaction.guild.id)
        if position < 1 or position > len(st.queue):
            await interaction.response.send_message("Invalid queue position!", ephemeral=True)
            return
        removed = st.queue.pop(position - 1)
        await interaction.response.send_message(f"🗑️ Removed **{removed.get('title','Unknown')}** from queue")

    @app_commands.command(name="nowplaying", description="Show currently playing song")
    async def nowplaying(self, interaction: discord.Interaction):
        st = self.state(interaction.guild.id)
        if not st.current:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
            return
        embed = discord.Embed(title="🎵 Now Playing", description=f"**{st.current.get('title','Unknown')}**", color=discord.Color.green())
        embed.add_field(name="Volume", value=f"{int(st.volume*100)}%", inline=True)
        url = st.current.get("webpage_url")
        if url:
            embed.add_field(name="URL", value=url, inline=False)
        thumb = st.current.get("thumbnail")
        if thumb:
            embed.set_thumbnail(url=thumb)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="refresh_cookies", description="Refresh YouTube cookies (Admin only)")
    async def refresh_cookies(self, interaction: discord.Interaction):
        config = await self.bot.db.get_guild_config(interaction.guild.id) if hasattr(self.bot, 'db') else {}
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator and not (admin_role_id and interaction.guild.get_role(admin_role_id) in interaction.user.roles):
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        self._ytdl = build_ytdl()
        await interaction.response.send_message("✅ Cookies refreshed (if file exists)")

    @app_commands.command(name="set_cookies", description="Set YouTube cookies (Admin only)")
    @app_commands.describe(cookies="YouTube cookies in Netscape format", attachment="Cookie file to upload (optional)")
    async def set_cookies(self, interaction: discord.Interaction, cookies: Optional[str] = None, attachment: Optional[discord.Attachment] = None):
        config = await self.bot.db.get_guild_config(interaction.guild.id) if hasattr(self.bot, 'db') else {}
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator and not (admin_role_id and interaction.guild.get_role(admin_role_id) in interaction.user.roles):
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            content = None
            if attachment:
                if attachment.size > 1024 * 1024:
                    await interaction.followup.send("❌ Cookie file is too large! Maximum size is 1MB.", ephemeral=True)
                    return
                content = (await attachment.read()).decode("utf-8")
                src = "uploaded file"
            elif cookies:
                content = cookies
                src = "text input"
            else:
                await interaction.followup.send("Provide cookies via text or file upload.", ephemeral=True)
                return
            if not content.strip():
                await interaction.followup.send("❌ Invalid cookie format!", ephemeral=True)
                return
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                f.write(content)
            self._ytdl = build_ytdl()
            await interaction.followup.send(f"✅ Cookies set from {src}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error setting cookies: {e}")
            await interaction.followup.send(f"❌ Error setting cookies: {str(e)}", ephemeral=True)

    @app_commands.command(name="cookie_status", description="Check cookie status (Admin only)")
    async def cookie_status(self, interaction: discord.Interaction):
        config = await self.bot.db.get_guild_config(interaction.guild.id) if hasattr(self.bot, 'db') else {}
        admin_role_id = config.get('admin_role') if config else None
        if not interaction.user.guild_permissions.administrator and not (admin_role_id and interaction.guild.get_role(admin_role_id) in interaction.user.roles):
            await interaction.response.send_message("❌ You need administrator permissions to use this command!", ephemeral=True)
            return
        exists = os.path.exists(COOKIES_FILE)
        embed = discord.Embed(title="🍪 Cookie Status", color=discord.Color.blue())
        embed.add_field(name="Cookie File", value="✅ Found" if exists else "❌ Not Found", inline=False)
        embed.add_field(name="File Path", value=COOKIES_FILE, inline=False)
        if exists:
            try:
                file_age = int(time.time() - os.path.getmtime(COOKIES_FILE))
                hours = file_age // 3600
                minutes = (file_age % 3600) // 60
                embed.add_field(name="File Age", value=f"{hours}h {minutes}m", inline=True)
            except Exception:
                embed.add_field(name="File Age", value="Unknown", inline=True)
        else:
            embed.add_field(name="Note", value="Use `/set_cookies` to add cookies for better YouTube access", inline=False)
        await interaction.response.send_message(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member == self.bot.user and before.channel and not after.channel:
            gid = before.channel.guild.id
            self.states.pop(gid, None)
            task = self._inactivity_tasks.pop(gid, None)
            if task:
                task.cancel()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MusicCog(bot)) 