import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, time, timezone
from typing import Optional
import calendar
import re

class BirthdayCog(commands.Cog):
    """Birthday tracking and announcement system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.birthday_check.start()
    
    def cog_unload(self):
        self.birthday_check.cancel()
    
    @tasks.loop(hours=24)
    async def birthday_check(self):
        """Check for birthdays daily"""
        now = datetime.now()
        
        for guild in self.bot.guilds:
            try:
                # Get today's birthdays
                users_with_birthdays = await self.bot.db.get_birthdays_for_date(
                    guild.id, now.month, now.day
                )
                
                if users_with_birthdays:
                    await self._announce_birthdays(guild, users_with_birthdays)
            
            except Exception as e:
                print(f"Error checking birthdays for guild {guild.id}: {e}")
    
    @birthday_check.before_loop
    async def before_birthday_check(self):
        """Wait until bot is ready"""
        await self.bot.wait_until_ready()
    
    async def _announce_birthdays(self, guild, user_ids):
        """Announce birthdays in the configured channel"""
        config = await self.bot.db.get_guild_config(guild.id)
        birthday_channel_id = config.get('birthday_channel')
        
        if not birthday_channel_id:
            return  # No birthday channel configured
        
        birthday_channel = self.bot.get_channel(birthday_channel_id)
        if not birthday_channel:
            return  # Channel not found
        
        # Get birthday role if configured
        birthday_role = None
        birthday_role_id = config.get('birthday_role')
        if birthday_role_id:
            birthday_role = guild.get_role(birthday_role_id)
        
        # Announce each birthday
        for user_id in user_ids:
            member = guild.get_member(user_id)
            if member:
                # Assign birthday role if configured
                if birthday_role and birthday_role not in member.roles:
                    try:
                        await member.add_roles(birthday_role, reason="Birthday role")
                    except discord.Forbidden:
                        pass
                
                # Create birthday announcement
                embed = discord.Embed(
                    title="🎉 Happy Birthday! 🎉",
                    description=f"Wishing {member.mention} a wonderful birthday!",
                    color=discord.Color.gold(),
                    timestamp=datetime.utcnow()
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                
                try:
                    await birthday_channel.send(embed=embed)
                except discord.Forbidden:
                    pass
    
    def _parse_birthday(self, birthday_str):
        """Parse birthday string into month and day"""
        # Try MM/DD format
        date_match = re.match(r'^(\d{1,2})/(\d{1,2})$', birthday_str)
        if date_match:
            month, day = int(date_match.group(1)), int(date_match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return month, day
        
        # Try "Month Day" format
        month_names = {
            'january': 1, 'jan': 1,
            'february': 2, 'feb': 2,
            'march': 3, 'mar': 3,
            'april': 4, 'apr': 4,
            'may': 5,
            'june': 6, 'jun': 6,
            'july': 7, 'jul': 7,
            'august': 8, 'aug': 8,
            'september': 9, 'sep': 9, 'sept': 9,
            'october': 10, 'oct': 10,
            'november': 11, 'nov': 11,
            'december': 12, 'dec': 12
        }
        
        parts = birthday_str.lower().split()
        if len(parts) == 2:
            month_part, day_part = parts
            if month_part in month_names:
                try:
                    month = month_names[month_part]
                    day = int(day_part)
                    if 1 <= day <= 31:
                        return month, day
                except ValueError:
                    pass
        
        return None, None
    
    def _validate_date(self, month, day):
        """Validate that the date is real"""
        try:
            # Check if the date is valid
            datetime(2020, month, day)  # Use 2020 (leap year) to handle Feb 29
            return True
        except ValueError:
            return False
    
    @app_commands.command(name="setbirthday", description="Set your birthday")
    @app_commands.describe(date="Your birthday (MM/DD or 'Month Day' format)")
    async def setbirthday(self, interaction: discord.Interaction, date: str):
        """Set user's birthday"""
        month, day = self._parse_birthday(date)
        
        if month is None or day is None:
            await interaction.response.send_message(
                "Invalid date format! Use MM/DD (e.g., 07/21) or 'Month Day' (e.g., July 21)",
                ephemeral=True
            )
            return
        
        if not self._validate_date(month, day):
            await interaction.response.send_message(
                "Invalid date! Please check the month and day.",
                ephemeral=True
            )
            return
        
        # Save birthday
        await self.bot.db.set_user_birthday(
            interaction.user.id, interaction.guild.id, month, day
        )
        
        # Format the date nicely
        month_name = calendar.month_name[month]
        embed = discord.Embed(
            title="🎂 Birthday Set!",
            description=f"Your birthday has been set to **{month_name} {day}**",
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="birthday", description="View someone's birthday")
    @app_commands.describe(user="User to check birthday for (optional)")
    async def birthday(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        """View user's birthday"""
        target_user = user or interaction.user
        
        # Get birthday from database
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute(
                'SELECT birth_month, birth_day FROM user_birthdays WHERE user_id = ? AND guild_id = ?',
                (target_user.id, interaction.guild.id)
            ) as cursor:
                result = await cursor.fetchone()
        
        if not result:
            embed = discord.Embed(
                title="🎂 Birthday",
                description=f"{target_user.display_name} hasn't set their birthday yet.",
                color=discord.Color.red()
            )
        else:
            month, day = result
            month_name = calendar.month_name[month]
            
            # Calculate next birthday
            now = datetime.now()
            this_year = now.year
            birthday_this_year = datetime(this_year, month, day)
            
            if birthday_this_year < now:
                next_birthday = datetime(this_year + 1, month, day)
            else:
                next_birthday = birthday_this_year
            
            days_until = (next_birthday - now).days
            
            embed = discord.Embed(
                title="🎂 Birthday",
                description=f"{target_user.display_name}'s birthday is **{month_name} {day}**",
                color=discord.Color.blue()
            )
            
            if days_until == 0:
                embed.add_field(name="🎉", value="It's their birthday today!", inline=False)
            elif days_until == 1:
                embed.add_field(name="⏰", value="Tomorrow!", inline=False)
            else:
                embed.add_field(name="⏰", value=f"In {days_until} days", inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="birthdays", description="List upcoming birthdays")
    @app_commands.describe(month="Month to show birthdays for (optional)")
    async def birthdays(self, interaction: discord.Interaction, month: Optional[str] = None):
        """List birthdays for a month"""
        if month:
            # Parse month name/number
            month_names = {
                'january': 1, 'jan': 1, '1': 1,
                'february': 2, 'feb': 2, '2': 2,
                'march': 3, 'mar': 3, '3': 3,
                'april': 4, 'apr': 4, '4': 4,
                'may': 5, '5': 5,
                'june': 6, 'jun': 6, '6': 6,
                'july': 7, 'jul': 7, '7': 7,
                'august': 8, 'aug': 8, '8': 8,
                'september': 9, 'sep': 9, 'sept': 9, '9': 9,
                'october': 10, 'oct': 10, '10': 10,
                'november': 11, 'nov': 11, '11': 11,
                'december': 12, 'dec': 12, '12': 12
            }
            
            month_num = month_names.get(month.lower())
            if not month_num:
                await interaction.response.send_message("Invalid month!", ephemeral=True)
                return
        else:
            # Use current month
            month_num = datetime.now().month
        
        # Get birthdays for the month
        birthdays = await self.bot.db.get_birthdays_for_month(interaction.guild.id, month_num)
        
        if not birthdays:
            month_name = calendar.month_name[month_num]
            embed = discord.Embed(
                title="🎂 Birthdays",
                description=f"No birthdays in {month_name}",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Sort by day
        birthdays.sort(key=lambda x: x['day'])
        
        month_name = calendar.month_name[month_num]
        embed = discord.Embed(
            title=f"🎂 Birthdays in {month_name}",
            color=discord.Color.blue()
        )
        
        description = ""
        for birthday in birthdays:
            user = self.bot.get_user(birthday['user_id'])
            if user:
                # Check if it's today
                today = datetime.now()
                if month_num == today.month and birthday['day'] == today.day:
                    description += f"🎉 **{user.display_name}** - {month_name} {birthday['day']} (Today!)\n"
                else:
                    description += f"🎂 **{user.display_name}** - {month_name} {birthday['day']}\n"
        
        embed.description = description or "No birthdays found"
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="removebirthday", description="Remove your birthday")
    async def removebirthday(self, interaction: discord.Interaction):
        """Remove user's birthday"""
        import aiosqlite
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            await db.execute(
                'DELETE FROM user_birthdays WHERE user_id = ? AND guild_id = ?',
                (interaction.user.id, interaction.guild.id)
            )
            await db.commit()
        
        embed = discord.Embed(
            title="🗑️ Birthday Removed",
            description="Your birthday has been removed from this server.",
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="allbirthdays", description="Show all birthdays in chronological order")
    async def allbirthdays(self, interaction: discord.Interaction):
        """Show all birthdays in the server sorted chronologically"""
        import aiosqlite
        
        # Get all birthdays for the guild
        async with aiosqlite.connect(self.bot.db.db_file) as db:
            async with db.execute(
                'SELECT user_id, birth_month, birth_day FROM user_birthdays WHERE guild_id = ? ORDER BY birth_month, birth_day',
                (interaction.guild.id,)
            ) as cursor:
                birthdays = await cursor.fetchall()
        
        if not birthdays:
            embed = discord.Embed(
                title="🎂 All Birthdays",
                description="No birthdays have been set in this server yet.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Group birthdays by month
        monthly_birthdays = {}
        for user_id, month, day in birthdays:
            if month not in monthly_birthdays:
                monthly_birthdays[month] = []
            
            user = self.bot.get_user(user_id)
            if user:  # Only include users that are still accessible
                monthly_birthdays[month].append({
                    'user': user,
                    'day': day,
                    'month': month
                })
        
        # Create embed
        embed = discord.Embed(
            title="🎂 All Birthdays",
            description="All birthdays in chronological order",
            color=discord.Color.blue()
        )
        
        # Get current date for highlighting today's birthdays
        today = datetime.now()
        
        # Add each month's birthdays
        for month in range(1, 13):
            if month not in monthly_birthdays:
                continue
            
            month_name = calendar.month_name[month]
            birthday_list = []
            
            # Sort by day within the month
            monthly_birthdays[month].sort(key=lambda x: x['day'])
            
            for birthday in monthly_birthdays[month]:
                user = birthday['user']
                day = birthday['day']
                
                # Check if it's today
                if month == today.month and day == today.day:
                    birthday_list.append(f"🎉 **{user.display_name}** - {day} (Today!)")
                else:
                    birthday_list.append(f"🎂 **{user.display_name}** - {day}")
            
            # Add field for this month (limit to 1024 characters per field)
            field_value = "\n".join(birthday_list)
            if len(field_value) > 1024:
                # Split into multiple fields if too long
                chunks = []
                current_chunk = ""
                for line in birthday_list:
                    if len(current_chunk + line + "\n") > 1024:
                        chunks.append(current_chunk.strip())
                        current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
                if current_chunk:
                    chunks.append(current_chunk.strip())
                
                for i, chunk in enumerate(chunks):
                    field_name = f"{month_name}" if i == 0 else f"{month_name} (cont.)"
                    embed.add_field(name=field_name, value=chunk, inline=True)
            else:
                embed.add_field(name=month_name, value=field_value, inline=True)
        
        # Add footer with total count
        total_birthdays = sum(len(birthdays) for birthdays in monthly_birthdays.values())
        embed.set_footer(text=f"Total: {total_birthdays} birthdays")
        
        await interaction.response.send_message(embed=embed)
    
    # Configuration Commands
    @app_commands.command(name="birthday-config", description="Configure birthday settings (Admin only)")
    @app_commands.describe(
        channel="Channel for birthday announcements",
        role="Role to assign on birthdays (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def birthday_config(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None
    ):
        """Configure birthday settings"""
        config_updates = {}
        
        if channel is not None:
            # Check permissions
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "I don't have permission to send messages in that channel!",
                    ephemeral=True
                )
                return
            config_updates['birthday_channel'] = channel.id
        
        if role is not None:
            # Check if bot can manage the role
            if role >= interaction.guild.me.top_role:
                await interaction.response.send_message(
                    "I cannot manage that role (it's higher than my highest role)!",
                    ephemeral=True
                )
                return
            config_updates['birthday_role'] = role.id
        
        if not config_updates:
            # Show current configuration
            config = await self.bot.db.get_guild_config(interaction.guild.id)
            embed = discord.Embed(
                title="🎂 Birthday Configuration",
                color=discord.Color.blue()
            )
            
            # Birthday channel
            birthday_channel_id = config.get('birthday_channel')
            if birthday_channel_id:
                channel_obj = self.bot.get_channel(birthday_channel_id)
                channel_text = channel_obj.mention if channel_obj else "Deleted Channel"
            else:
                channel_text = "Not configured"
            embed.add_field(name="Birthday Channel", value=channel_text, inline=True)
            
            # Birthday role
            birthday_role_id = config.get('birthday_role')
            if birthday_role_id:
                role_obj = interaction.guild.get_role(birthday_role_id)
                role_text = role_obj.mention if role_obj else "Deleted Role"
            else:
                role_text = "None"
            embed.add_field(name="Birthday Role", value=role_text, inline=True)
            
            await interaction.response.send_message(embed=embed)
        else:
            # Update configuration
            await self.bot.db.update_guild_config(interaction.guild.id, **config_updates)
            
            embed = discord.Embed(
                title="✅ Birthday Configuration Updated",
                color=discord.Color.green()
            )
            
            for key, value in config_updates.items():
                if key == 'birthday_channel':
                    channel_obj = self.bot.get_channel(value)
                    embed.add_field(name="Birthday Channel", value=channel_obj.mention if channel_obj else "Unknown", inline=True)
                elif key == 'birthday_role':
                    role_obj = interaction.guild.get_role(value)
                    embed.add_field(name="Birthday Role", value=role_obj.mention if role_obj else "Unknown", inline=True)
            
            await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Remove birthday role when day changes (cleanup)"""
        # This is a simple implementation - in a production bot you'd want
        # a more sophisticated system to track when to remove birthday roles
        pass

async def setup(bot):
    await bot.add_cog(BirthdayCog(bot)) 