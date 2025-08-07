import discord
from discord.ext import commands
from discord import app_commands
import random
import re
from typing import Optional, List, Tuple
import google.generativeai as genai
from config import Config
import asyncio


class DnDCog(commands.Cog):
    """D&D related functionality including dice rolling and action parsing"""
    
    def __init__(self, bot):
        self.bot = bot
        self.setup_ai()
    
    def setup_ai(self):
        """Setup Gemini AI for D&D action parsing"""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False
            print("Warning: Gemini API key not configured. D&D action parsing disabled.")
    
    def roll_dice(self, dice_string: str) -> Tuple[List[int], int, str]:
        """
        Roll dice based on standard notation (e.g., '2d6+3', '1d20', '4d8-2')
        Returns: (individual_rolls, total, breakdown_string)
        """
        # Parse dice notation using regex
        pattern = r'(\d+)d(\d+)([+-]\d+)?'
        match = re.match(pattern, dice_string.strip().lower().replace(' ', ''))
        
        if not match:
            raise ValueError(f"Invalid dice notation: {dice_string}")
        
        num_dice = int(match.group(1))
        die_size = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        # Validate input
        if num_dice <= 0 or num_dice > 100:
            raise ValueError("Number of dice must be between 1 and 100")
        if die_size <= 0 or die_size > 1000:
            raise ValueError("Die size must be between 1 and 1000")
        
        # Roll the dice
        rolls = [random.randint(1, die_size) for _ in range(num_dice)]
        dice_total = sum(rolls)
        final_total = dice_total + modifier
        
        # Create breakdown string
        if len(rolls) == 1:
            if modifier == 0:
                breakdown = f"🎲 **{rolls[0]}**"
            else:
                breakdown = f"🎲 **{rolls[0]}** {'+' if modifier > 0 else ''}{modifier} = **{final_total}**"
        else:
            rolls_str = " + ".join(map(str, rolls))
            if modifier == 0:
                breakdown = f"🎲 [{rolls_str}] = **{final_total}**"
            else:
                breakdown = f"🎲 [{rolls_str}] {'+' if modifier > 0 else ''}{modifier} = **{final_total}**"
        
        return rolls, final_total, breakdown
    
    @app_commands.command(name="roll", description="Roll dice using standard notation (e.g., 2d6+3)")
    @app_commands.describe(dice="Dice to roll (e.g., 1d20, 2d6+3, 4d8-2)")
    async def roll_dice_command(self, interaction: discord.Interaction, dice: str):
        """Roll dice command"""
        try:
            rolls, total, breakdown = self.roll_dice(dice)
            
            embed = discord.Embed(
                title=f"🎲 Dice Roll: {dice.upper()}",
                description=breakdown,
                color=discord.Color.blue()
            )
            
            # Add some flair for critical hits/fails on d20s
            if dice.strip().lower() in ['1d20', 'd20'] and len(rolls) == 1:
                if rolls[0] == 20:
                    embed.add_field(name="🌟", value="**NATURAL 20!**", inline=False)
                    embed.color = discord.Color.gold()
                elif rolls[0] == 1:
                    embed.add_field(name="💀", value="**NATURAL 1!**", inline=False)
                    embed.color = discord.Color.red()
            
            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed)
            
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ **Error:** {str(e)}\n\n**Examples:**\n• `1d20` - Roll a d20\n• `2d6+3` - Roll 2d6 and add 3\n• `4d8-2` - Roll 4d8 and subtract 2",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An unexpected error occurred: {str(e)}",
                ephemeral=True
            )
    
    async def _parse_dnd_action(self, action: str) -> Optional[str]:
        """Use Gemini AI to parse D&D action and determine dice to roll"""
        if not self.ai_enabled:
            return None
        
        try:
            prompt = f"""
You are a D&D 5e expert. Given the following D&D action/spell/ability, determine what dice need to be rolled for damage or effects.

Action: {action}

Please respond with ONLY the dice notation (e.g., "2d6", "1d8+3", "4d6") that should be rolled for this action. If it's a spell, assume it's cast at the base level unless otherwise specified. If the action doesn't involve dice rolling, respond with "NO_DICE".

Examples:
- "level 3 smite" → "3d8"
- "chromatic orb level 1" → "3d8"
- "chromatic orb level 4" → "6d8"
- "fireball" → "8d6"
- "healing word level 1" → "1d4"
- "sword attack" → "1d8"
- "shortbow attack" → "1d6"
- "cantrip fire bolt" → "1d10"

Respond with just the dice notation, nothing else.
"""
            
            response = await asyncio.to_thread(
                self.model.generate_content, prompt
            )
            
            dice_notation = response.text.strip().upper()
            
            # Validate the response
            if dice_notation == "NO_DICE":
                return None
            
            # Basic validation of dice notation
            if not re.match(r'^\d+d\d+([+-]\d+)?$', dice_notation.lower().replace(' ', '')):
                return None
            
            return dice_notation.lower()
            
        except Exception as e:
            print(f"Error parsing D&D action: {e}")
            return None
    
    @app_commands.command(name="dnd-action", description="Roll dice for a D&D action, spell, or ability")
    @app_commands.describe(action="D&D action, spell, or ability (e.g., 'level 3 smite', 'chromatic orb level 4', 'fireball')")
    async def dnd_action_command(self, interaction: discord.Interaction, action: str):
        """Parse D&D action and roll appropriate dice"""
        if not self.ai_enabled:
            await interaction.response.send_message(
                "❌ **AI Not Available:** This command requires Gemini AI to be configured. Please use the `/roll` command directly with dice notation instead.",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Parse the action using AI
            dice_notation = await self._parse_dnd_action(action)
            
            if dice_notation is None:
                embed = discord.Embed(
                    title="🤷 No Dice Required",
                    description=f"The action **{action}** doesn't appear to require dice rolling, or I couldn't determine the appropriate dice.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💡 Tip",
                    value="Try being more specific or use the `/roll` command directly with dice notation (e.g., `/roll 2d6+3`)",
                    inline=False
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Roll the dice
            rolls, total, breakdown = self.roll_dice(dice_notation)
            
            embed = discord.Embed(
                title=f"⚔️ D&D Action: {action.title()}",
                description=f"**Dice:** {dice_notation.upper()}\n{breakdown}",
                color=discord.Color.purple()
            )
            
            # Add critical hit detection for damage rolls
            if any(die_size in dice_notation for die_size in ['d6', 'd8', 'd10', 'd12']):
                max_possible = dice_notation.count('d') * int(re.search(r'd(\d+)', dice_notation).group(1))
                if total >= max_possible * 0.9:  # 90% or higher of max damage
                    embed.add_field(name="🔥", value="**Excellent damage!**", inline=False)
                    embed.color = discord.Color.gold()
            
            embed.set_footer(text=f"Parsed by AI • Requested by {interaction.user.display_name}")
            
            await interaction.followup.send(embed=embed)
            
        except ValueError as e:
            await interaction.followup.send(
                f"❌ **Dice Error:** {str(e)}",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error:** Could not process the D&D action. Please try again or use the `/roll` command directly.\n\nError details: {str(e)}",
                ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(DnDCog(bot))