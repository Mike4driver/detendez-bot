import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, Dict, Any
from datetime import datetime

class GeographicCog(commands.Cog):
    """Geographic reaction roll system for US regions"""
    
    def __init__(self, bot):
        self.bot = bot
        # Define the regional emojis
        self.region_emojis = {
            "🌊": "West Coast",  # Ocean wave for West Coast
            "🏙️": "East Coast",  # City skyline for East Coast  
            "🏔️": "North",       # Mountain for North
            "🌵": "South"        # Cactus for South
        }
        self.emoji_to_region = {v: k for k, v in self.region_emojis.items()}
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle geographic reactions being added"""
        await self._handle_geographic_reaction(payload, added=True)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle geographic reactions being removed"""
        await self._handle_geographic_reaction(payload, added=False)
    
    async def _handle_geographic_reaction(self, payload, added=True):
        """Handle geographic reaction changes"""
        # Ignore DMs and bot reactions
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        
        # Check if this message is a geographic poll
        is_geographic_poll = await self.bot.db.is_geographic_poll(payload.message_id, payload.guild_id)
        if not is_geographic_poll:
            return
        
        # Check if this is one of our geographic emojis
        emoji_str = str(payload.emoji)
        if emoji_str not in self.region_emojis:
            return
        
        region = self.region_emojis[emoji_str]
        
        if added:
            # Remove user's previous selections for this poll
            await self.bot.db.remove_user_geographic_selection(
                payload.user_id, payload.message_id, payload.guild_id
            )
            
            # Add new selection
            await self.bot.db.add_geographic_selection(
                payload.user_id, payload.message_id, payload.guild_id, region
            )
            
            # Remove user's reactions to other emojis
            guild = self.bot.get_guild(payload.guild_id)
            channel = guild.get_channel(payload.channel_id)
            try:
                message = await channel.fetch_message(payload.message_id)
                user = guild.get_member(payload.user_id)
                
                for reaction in message.reactions:
                    emoji_str_check = str(reaction.emoji)
                    if emoji_str_check in self.region_emojis and emoji_str_check != emoji_str:
                        await message.remove_reaction(reaction.emoji, user)
            except (discord.NotFound, discord.Forbidden):
                pass
        else:
            # Remove selection when reaction is removed
            await self.bot.db.remove_geographic_selection(
                payload.user_id, payload.message_id, payload.guild_id, region
            )
    
    @app_commands.command(name="geographic-poll", description="Create a geographic poll for US regions")
    @app_commands.describe(
        title="Title for the poll",
        description="Description of what the poll is for"
    )
    async def create_geographic_poll(
        self,
        interaction: discord.Interaction,
        title: str = "What region of the US are you from?",
        description: str = "React with your region!"
    ):
        """Create a geographic reaction poll"""
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        # Add region explanations
        regions_text = []
        for emoji, region in self.region_emojis.items():
            if region == "West Coast":
                regions_text.append(f"{emoji} **West Coast** - California, Oregon, Washington")
            elif region == "East Coast":
                regions_text.append(f"{emoji} **East Coast** - New York, Florida, Maine, etc.")
            elif region == "North":
                regions_text.append(f"{emoji} **North** - Alaska, Minnesota, North Dakota, etc.")
            elif region == "South":
                regions_text.append(f"{emoji} **South** - Texas, Arizona, Nevada, etc.")
        
        embed.add_field(
            name="Regions",
            value="\n".join(regions_text),
            inline=False
        )
        
        embed.add_field(
            name="How to participate",
            value="React with the emoji that matches your region. You can only select one region at a time.",
            inline=False
        )
        
        embed.set_footer(text=f"Poll created by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
        
        # Get the message to add reactions
        message = await interaction.original_response()
        
        # Add all reaction emojis
        for emoji in self.region_emojis.keys():
            await message.add_reaction(emoji)
        
        # Register this as a geographic poll in the database
        await self.bot.db.add_geographic_poll(message.id, interaction.guild.id, title, interaction.channel.id)
    
    @app_commands.command(name="geographic-results", description="Show results of a geographic poll")
    @app_commands.describe(message_id="ID of the poll message")
    async def show_geographic_results(
        self,
        interaction: discord.Interaction,
        message_id: str
    ):
        """Show results of a geographic poll"""
        
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Please provide a valid message ID.", ephemeral=True)
            return
        
        # Check if this is a geographic poll
        poll_data = await self.bot.db.get_geographic_poll(msg_id, interaction.guild.id)
        if not poll_data:
            await interaction.response.send_message("This message is not a geographic poll.", ephemeral=True)
            return
        
        # Get results
        results = await self.bot.db.get_geographic_results(msg_id, interaction.guild.id)
        
        embed = discord.Embed(
            title=f"📊 Results: {poll_data['title']}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        total_votes = sum(results.values())
        
        if total_votes == 0:
            embed.description = "No votes yet!"
        else:
            results_text = []
            for emoji, region in self.region_emojis.items():
                count = results.get(region, 0)
                percentage = (count / total_votes) * 100 if total_votes > 0 else 0
                results_text.append(f"{emoji} **{region}**: {count} votes ({percentage:.1f}%)")
            
            embed.add_field(
                name="Results",
                value="\n".join(results_text),
                inline=False
            )
            
            embed.add_field(
                name="Total Votes",
                value=str(total_votes),
                inline=True
            )
        
        # Add link to original poll
        try:
            channel = interaction.guild.get_channel(poll_data['channel_id'])
            if channel:
                message_link = f"https://discord.com/channels/{interaction.guild.id}/{channel.id}/{msg_id}"
                embed.add_field(
                    name="Original Poll",
                    value=f"[Click here to view]({message_link})",
                    inline=True
                )
        except:
            pass
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="my-region", description="Check what region you've selected")
    async def check_my_region(self, interaction: discord.Interaction):
        """Check user's current region selection"""
        
        # Get all user's selections in this guild
        selections = await self.bot.db.get_user_geographic_selections(
            interaction.user.id, interaction.guild.id
        )
        
        if not selections:
            await interaction.response.send_message(
                "You haven't participated in any geographic polls yet!", 
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="🗺️ Your Geographic Selections",
            color=discord.Color.blue()
        )
        
        for selection in selections:
            region = selection['region']
            emoji = self.emoji_to_region.get(region, "❓")
            poll_title = selection['poll_title']
            
            embed.add_field(
                name=f"{emoji} {region}",
                value=f"Poll: {poll_title}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GeographicCog(bot)) 