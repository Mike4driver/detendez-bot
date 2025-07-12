import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import google.generativeai as genai
from config import Config
from datetime import datetime, timedelta
import json
from typing import Optional
import pytz
from dateutil.parser import parse as date_parse
from ics import Calendar, Event
import io

class SchedulerCog(commands.Cog):
    """Cog for scheduling Discord events using AI"""

    def __init__(self, bot):
        self.bot = bot
        self.setup_ai()

    def setup_ai(self):
        """Setup Gemini AI"""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False

    def _create_gcal_link(self, title, start_time, end_time, description, location):
        """Generates a Google Calendar link"""
        base_url = "https://www.google.com/calendar/render?action=TEMPLATE"
        
        # Format times to ISO 8601 UTC without special characters
        start_utc = start_time.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        end_utc = end_time.astimezone(pytz.utc).strftime('%Y%m%dT%H%M%SZ')
        
        params = {
            'text': title,
            'dates': f"{start_utc}/{end_utc}",
            'details': description,
            'location': location,
            'trp': 'false' # Show as busy
        }
        
        import urllib.parse
        return f"{base_url}&{urllib.parse.urlencode(params)}"

    def _create_ics_file_content(self, title, start_time, end_time, description, location):
        """Generates the content for an .ics file"""
        c = Calendar()
        e = Event()
        e.name = title
        e.begin = start_time
        e.end = end_time
        e.description = description
        e.location = location
        c.events.add(e)
        return str(c)

    def _get_system_prompt(self):
        return """
You are a helpful assistant that schedules events. Your task is to extract event details from a user's prompt and return them as a JSON object.

The user will provide a prompt and the current date to help with relative date calculations (e.g., "next Friday").

You must extract the following fields:
- "title": The title of the event.
- "start_time": The start date and time in ISO 8601 format (YYYY-MM-DDTHH:MM:SS).
- "end_time": The end date and time in ISO 8601 format. If not specified, calculate it as 1 hour after the start time.
- "description": A brief description of the event. If not provided, use the event title.
- "location": The physical or virtual location of the event. If not specified, this should be an empty string.

Rules:
1. Always return a valid JSON object.
2. If a value cannot be determined, return a sensible default (e.g., empty string for location).
3. Do not add any text or explanation outside of the JSON object in your response.
4. The start and end times must be in ISO 8601 format.
"""

    @app_commands.command(name="schedule", description="Schedules a Discord event using natural language.")
    @app_commands.describe(
        prompt="Describe the event you want to schedule (e.g., 'Team meeting next Friday at 3 PM about Q3 planning').",
        timezone="Your timezone (e.g., 'America/New_York'). Defaults to UTC."
    )
    async def schedule(self, interaction: discord.Interaction, prompt: str, timezone: Optional[str] = "UTC"):
        await interaction.response.defer(ephemeral=True)

        if not self.ai_enabled:
            await interaction.followup.send("❌ The AI scheduling feature is disabled because no API key is configured.")
            return

        try:
            user_tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            await interaction.followup.send(
                f"❌ Unknown timezone: `{timezone}`. Please use a valid TZ database name (e.g., 'America/New_York', 'Europe/London')."
            )
            return

        try:
            current_time_str = datetime.now(user_tz).strftime('%Y-%m-%d %H:%M:%S')
            full_prompt = (
                f"Current time: {current_time_str} ({timezone})\n"
                f"User prompt: \"{prompt}\""
            )

            response = await asyncio.to_thread(
                self.model.generate_content,
                [self._get_system_prompt(), full_prompt]
            )

            # Clean up the response to get only the JSON part
            json_response_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            event_details = json.loads(json_response_text)
            
            title = event_details.get("title")
            start_time_str = event_details.get("start_time")
            end_time_str = event_details.get("end_time")
            description = event_details.get("description", "")
            location = event_details.get("location", "")

            if not all([title, start_time_str, end_time_str]):
                raise ValueError("AI response was missing one or more required fields (title, start_time, end_time).")

            # Parse times and make them timezone-aware
            start_time = date_parse(start_time_str)
            if start_time.tzinfo is None:
                start_time = user_tz.localize(start_time)
            
            end_time = date_parse(end_time_str)
            if end_time.tzinfo is None:
                end_time = user_tz.localize(end_time)

            # Create the Discord Scheduled Event
            created_event = await interaction.guild.create_scheduled_event(
                name=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                entity_type=discord.EntityType.external,
                location=location or "Not specified",
                privacy_level=discord.PrivacyLevel.guild_only
            )
            
            # Generate calendar links
            gcal_link = self._create_gcal_link(title, start_time, end_time, description, location)
            ics_content = self._create_ics_file_content(title, start_time, end_time, description, location)
            ics_file = discord.File(fp=io.BytesIO(ics_content.encode('utf-8')), filename="event.ics")
            
            # Send confirmation
            embed = discord.Embed(
                title="✅ Event Scheduled Successfully!",
                description=f"I've scheduled **{title}** for you. You can see it in the server's events tab.",
                color=discord.Color.green()
            )
            embed.add_field(name="📅 Start Time", value=f"<t:{int(start_time.timestamp())}:F>", inline=True)
            embed.add_field(name="🕒 End Time", value=f"<t:{int(end_time.timestamp())}:F>", inline=True)
            if location:
                embed.add_field(name="📍 Location", value=location, inline=False)
            if description:
                 embed.add_field(name="📝 Description", value=description, inline=False)

            embed.set_footer(text=f"Timezone: {timezone}. If this is wrong, please re-run with the correct timezone.")
            
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="View Discord Event", url=created_event.url))
            view.add_item(discord.ui.Button(label="Add to Google Calendar", url=gcal_link))

            await interaction.followup.send(embed=embed, view=view, files=[ics_file])

        except json.JSONDecodeError:
            await interaction.followup.send("❌ The AI returned an invalid response. I couldn't understand the event details. Please try rephrasing your request.")
        except Exception as e:
            await interaction.followup.send(f"❌ An unexpected error occurred: {e}")


async def setup(bot):
    await bot.add_cog(SchedulerCog(bot)) 