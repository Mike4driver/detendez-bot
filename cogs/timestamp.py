import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
import re
import pytz

class TimestampCog(commands.Cog):
    """Timestamp conversion system for detecting and converting time/date patterns"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def _compile_patterns(self):
        """Compile regex patterns for time/date detection"""
        # Time-only patterns
        # 10pm, 10 pm, 10PM, 3:30, 15:00, 10 PM, etc.
        time_patterns = [
            r'\b(\d{1,2})\s*(am|pm|AM|PM)\b',  # 10pm, 10 pm
            r'\b(\d{1,2}):(\d{2})\s*(am|pm|AM|PM)?\b',  # 3:30, 3:30pm, 15:00
        ]
        
        # Date-only patterns
        # Dec 5, December 5th, 12/25, 12-25, etc.
        date_patterns = [
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\b',  # Dec 5, December 5th
            r'\b(\d{1,2})[/-](\d{1,2})\b',  # 12/25, 12-25
        ]
        
        # Combined patterns
        # Dec 5 at 3pm, tomorrow at 10am, etc.
        combined_patterns = [
            r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)\b',  # Dec 5 at 3pm
            r'\b(\d{1,2})[/-](\d{1,2})\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)\b',  # 12/25 at 3pm
            r'\b(tomorrow|today)\s+at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)\b',  # tomorrow at 10am
        ]
        
        return {
            'time': [re.compile(p, re.IGNORECASE) for p in time_patterns],
            'date': [re.compile(p, re.IGNORECASE) for p in date_patterns],
            'combined': [re.compile(p, re.IGNORECASE) for p in combined_patterns]
        }
    
    def _parse_time(self, match, timezone_str: str) -> Optional[int]:
        """Parse a time pattern and return Unix timestamp"""
        try:
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            
            groups = match.groups()
            
            # Pattern: (\d{1,2})\s*(am|pm)
            if len(groups) == 2 and groups[1] in ['am', 'pm', 'AM', 'PM']:
                hour = int(groups[0])
                period = groups[1].lower()
                
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                
                dt = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                # If time has passed today, assume tomorrow
                if dt < now:
                    dt += timedelta(days=1)
                
                return int(dt.timestamp())
            
            # Pattern: (\d{1,2}):(\d{2})\s*(am|pm)?
            elif len(groups) >= 2:
                hour = int(groups[0])
                minute = int(groups[1]) if groups[1] else 0
                period = groups[2].lower() if len(groups) > 2 and groups[2] else None
                
                # 24-hour format (no period)
                if period is None:
                    if hour >= 24 or minute >= 60:
                        return None
                    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    # 12-hour format
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                    
                    if hour >= 24 or minute >= 60:
                        return None
                    
                    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If time has passed today, assume tomorrow
                if dt < now:
                    dt += timedelta(days=1)
                
                return int(dt.timestamp())
            
        except Exception as e:
            print(f"Error parsing time: {e}")
            return None
    
    def _parse_date(self, match, timezone_str: str) -> Optional[int]:
        """Parse a date pattern and return Unix timestamp"""
        try:
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            
            groups = match.groups()
            month_names = {
                'jan': 1, 'january': 1,
                'feb': 2, 'february': 2,
                'mar': 3, 'march': 3,
                'apr': 4, 'april': 4,
                'may': 5,
                'jun': 6, 'june': 6,
                'jul': 7, 'july': 7,
                'aug': 8, 'august': 8,
                'sep': 9, 'september': 9, 'sept': 9,
                'oct': 10, 'october': 10,
                'nov': 11, 'november': 11,
                'dec': 12, 'december': 12
            }
            
            # Pattern: (Month) (\d{1,2}) or (\d{1,2})[/-](\d{1,2})
            if len(groups) == 2:
                month_str = groups[0].lower() if groups[0] else None
                day_str = groups[1]
                
                # Check if first group is a month name
                if month_str and month_str in month_names:
                    # Pattern: (Month) (\d{1,2})
                    month = month_names[month_str]
                    day = int(day_str)
                    year = now.year
                    
                    # If date has passed this year, assume next year
                    try:
                        dt = tz.localize(datetime(year, month, day))
                        if dt < now:
                            dt = tz.localize(datetime(year + 1, month, day))
                        return int(dt.timestamp())
                    except ValueError:
                        return None
                else:
                    # Pattern: (\d{1,2})[/-](\d{1,2}) - Try MM/DD format
                    try:
                        month = int(groups[0])
                        day = int(groups[1])
                        
                        if month < 1 or month > 12 or day < 1 or day > 31:
                            return None
                        
                        year = now.year
                        try:
                            dt = tz.localize(datetime(year, month, day))
                            if dt < now:
                                dt = tz.localize(datetime(year + 1, month, day))
                            return int(dt.timestamp())
                        except ValueError:
                            return None
                    except (ValueError, TypeError):
                        return None
            
        except Exception as e:
            print(f"Error parsing date: {e}")
            return None
    
    def _parse_combined(self, match, timezone_str: str) -> Optional[int]:
        """Parse a combined date/time pattern and return Unix timestamp"""
        try:
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)
            
            groups = match.groups()
            month_names = {
                'jan': 1, 'january': 1,
                'feb': 2, 'february': 2,
                'mar': 3, 'march': 3,
                'apr': 4, 'april': 4,
                'may': 5,
                'jun': 6, 'june': 6,
                'jul': 7, 'july': 7,
                'aug': 8, 'august': 8,
                'sep': 9, 'september': 9, 'sept': 9,
                'oct': 10, 'october': 10,
                'nov': 11, 'november': 11,
                'dec': 12, 'december': 12
            }
            
            # Pattern: (tomorrow|today) at (\d{1,2})(:(\d{2}))? (am|pm)
            # Check this first since it has a distinct first group
            if len(groups) >= 2 and groups[0] and groups[0].lower() in ['tomorrow', 'today']:
                day_keyword = groups[0].lower()
                hour = int(groups[1])
                # Minute is in group 2 if present, period is in group 3
                minute = int(groups[2]) if len(groups) > 2 and groups[2] and str(groups[2]).isdigit() else 0
                # Period is the last group
                period = groups[-1].lower() if groups[-1] else None
                
                if period:
                    if period == 'pm' and hour != 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0
                
                days_offset = 1 if day_keyword == 'tomorrow' else 0
                dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_offset)
                
                # If time has passed today and it's "today", assume tomorrow
                if day_keyword == 'today' and dt < now:
                    dt += timedelta(days=1)
                
                return int(dt.timestamp())
            
            # Pattern: (Month) (\d{1,2}) at (\d{1,2})(:(\d{2}))? (am|pm)
            # or Pattern: (\d{1,2})[/-](\d{1,2}) at (\d{1,2})(:(\d{2}))? (am|pm)
            elif len(groups) >= 4:
                month_str = groups[0]
                # Check if first group is a month name
                if month_str and isinstance(month_str, str) and month_str.lower() in month_names:
                    # Pattern: (Month) (\d{1,2}) at (\d{1,2})(:(\d{2}))? (am|pm)
                    month = month_names[month_str.lower()]
                    day = int(groups[1])
                    hour = int(groups[2])
                    # Minute is in group 3 if present, period is in group 4
                    minute = int(groups[3]) if len(groups) > 3 and groups[3] and str(groups[3]).isdigit() else 0
                    # Period is the last group
                    period = groups[-1].lower() if groups[-1] else None
                    
                    if period:
                        if period == 'pm' and hour != 12:
                            hour += 12
                        elif period == 'am' and hour == 12:
                            hour = 0
                    
                    year = now.year
                    try:
                        dt = tz.localize(datetime(year, month, day, hour, minute))
                        if dt < now:
                            dt = tz.localize(datetime(year + 1, month, day, hour, minute))
                        return int(dt.timestamp())
                    except ValueError:
                        return None
                else:
                    # Pattern: (\d{1,2})[/-](\d{1,2}) at (\d{1,2})(:(\d{2}))? (am|pm)
                    try:
                        month = int(groups[0])
                        day = int(groups[1])
                        hour = int(groups[2])
                        # Minute is in group 3 if present, period is in group 4
                        minute = int(groups[3]) if len(groups) > 3 and groups[3] and str(groups[3]).isdigit() else 0
                        # Period is the last group
                        period = groups[-1].lower() if groups[-1] else None
                        
                        if period:
                            if period == 'pm' and hour != 12:
                                hour += 12
                            elif period == 'am' and hour == 12:
                                hour = 0
                        
                        year = now.year
                        try:
                            dt = tz.localize(datetime(year, month, day, hour, minute))
                            if dt < now:
                                dt = tz.localize(datetime(year + 1, month, day, hour, minute))
                            return int(dt.timestamp())
                        except ValueError:
                            return None
                    except (ValueError, TypeError):
                        return None
            
        except Exception as e:
            print(f"Error parsing combined: {e}")
            return None
    
    def _detect_patterns(self, text: str) -> List[Tuple[str, int, str]]:
        """Detect time/date patterns in text and return list of (pattern_type, timestamp, matched_text)"""
        patterns = self._compile_patterns()
        results = []
        
        # Check combined patterns first (most specific)
        for pattern in patterns['combined']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                # We'll parse this later with timezone
                results.append(('combined', None, matched_text))
        
        # Check date patterns
        for pattern in patterns['date']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                # Skip if already matched by combined pattern
                if not any(r[2] == matched_text for r in results):
                    results.append(('date', None, matched_text))
        
        # Check time patterns
        for pattern in patterns['time']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                # Skip if already matched by combined pattern
                if not any(r[2] == matched_text for r in results):
                    results.append(('time', None, matched_text))
        
        return results
    
    async def _convert_patterns(self, text: str, timezone_str: str) -> List[Tuple[str, int, str]]:
        """Convert detected patterns to Discord timestamps"""
        patterns = self._compile_patterns()
        results = []
        
        # Check combined patterns first
        for pattern in patterns['combined']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                timestamp = self._parse_combined(match, timezone_str)
                if timestamp:
                    results.append(('combined', timestamp, matched_text))
                    # Mark this text as processed
                    text = text.replace(matched_text, '', 1)
        
        # Check date patterns
        for pattern in patterns['date']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                timestamp = self._parse_date(match, timezone_str)
                if timestamp:
                    results.append(('date', timestamp, matched_text))
                    # Mark this text as processed
                    text = text.replace(matched_text, '', 1)
        
        # Check time patterns
        for pattern in patterns['time']:
            for match in pattern.finditer(text):
                matched_text = match.group(0)
                timestamp = self._parse_time(match, timezone_str)
                if timestamp:
                    results.append(('time', timestamp, matched_text))
        
        return results
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listen for messages in channels with 'general' in the name"""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check if channel name contains "general"
        if not message.channel or not hasattr(message.channel, 'name'):
            return
        
        channel_name = message.channel.name.lower()
        if 'general' not in channel_name:
            return
        
        # Detect patterns in the message
        detected = self._detect_patterns(message.content)
        
        if not detected:
            return
        
        # Get user's timezone
        timezone = await self.bot.db.get_user_timezone(message.author.id)
        
        if not timezone:
            # User hasn't set timezone - prompt them (send as DM to avoid cluttering channel)
            try:
                await message.author.send(
                    f"I noticed you mentioned a time in {message.channel.mention}! Please set your timezone with `/set-timezone` so I can convert it for others."
                )
            except discord.Forbidden:
                # User has DMs disabled, fall back to reply
                await message.reply(
                    f"I noticed you mentioned a time! Please set your timezone with `/set-timezone` so I can convert it for others.",
                    mention_author=False
                )
            return
        
        # Convert patterns to Discord timestamps
        converted = await self._convert_patterns(message.content, timezone)
        
        if not converted:
            return
        
        # Build reply message
        reply_parts = []
        for pattern_type, timestamp, matched_text in converted:
            # Determine Discord timestamp format
            if pattern_type == 'time':
                format_char = 't'  # short time
            elif pattern_type == 'date':
                format_char = 'D'  # long date
            else:  # combined
                format_char = 'f'  # short date/time
            
            discord_timestamp = f"<t:{timestamp}:{format_char}>"
            reply_parts.append(f"{message.author.mention}'s **{matched_text}** is {discord_timestamp} in your timezone")
        
        if reply_parts:
            await message.reply("\n".join(reply_parts), mention_author=False)
    
    @app_commands.command(name="set-timezone", description="Set your timezone for timestamp conversion")
    @app_commands.describe(timezone="Your timezone (e.g., America/New_York, Europe/London, Asia/Tokyo)")
    async def set_timezone(self, interaction: discord.Interaction, timezone: str):
        """Set user's timezone"""
        # Validate timezone using pytz
        try:
            tz = pytz.timezone(timezone)
            # Test that it's valid by getting current time
            datetime.now(tz)
        except pytz.exceptions.UnknownTimeZoneError:
            await interaction.response.send_message(
                f"❌ Invalid timezone! Please use a valid timezone name like:\n"
                f"`America/New_York`, `Europe/London`, `Asia/Tokyo`, `America/Los_Angeles`, etc.\n"
                f"You can find a list at: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
                ephemeral=True
            )
            return
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error setting timezone: {str(e)}",
                ephemeral=True
            )
            return
        
        # Save timezone
        await self.bot.db.set_user_timezone(interaction.user.id, timezone)
        
        # Get current time in that timezone for confirmation
        current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
        
        embed = discord.Embed(
            title="✅ Timezone Set!",
            description=f"Your timezone has been set to **{timezone}**\n"
                       f"Current time in your timezone: **{current_time}**",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="my-timezone", description="View your current timezone setting")
    async def my_timezone(self, interaction: discord.Interaction):
        """View user's current timezone"""
        timezone = await self.bot.db.get_user_timezone(interaction.user.id)
        
        if not timezone:
            embed = discord.Embed(
                title="⏰ Timezone",
                description="You haven't set your timezone yet.\n"
                           "Use `/set-timezone` to configure it so I can convert times for you!",
                color=discord.Color.orange()
            )
        else:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S %Z")
            
            embed = discord.Embed(
                title="⏰ Your Timezone",
                description=f"**{timezone}**\n"
                           f"Current time: **{current_time}**",
                color=discord.Color.blue()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(TimestampCog(bot))

