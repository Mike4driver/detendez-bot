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
        # Parse dice notation using strict full-match regex
        pattern = r'^(\d+)d(\d+)([+-]\d+)?$'
        match = re.fullmatch(pattern, dice_string.strip().lower().replace(' ', ''))
        
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
        """Use Gemini AI (2-step) to parse a D&D action and determine dice to roll.
        Step 1: Ask the model for a verbose, rule-grounded analysis (not shown to users)
        Step 2: Ask the model to output ONLY the final dice notation or NO_DICE
        """
        if not self.ai_enabled:
            return None

        try:
            # Step 1: Obtain detailed analysis
            analysis_prompt = f"""
You are a D&D 5e expert rules assistant. Analyze the following action/spell/ability in detail.

Goals for analysis (do NOT provide the final dice notation here):
- Identify the feature (spell, weapon attack, class feature, smite, etc.) and its base damage/healing dice
- Consider slot level scaling when explicitly provided (e.g., "at 4th level")
- Use base level when no slot level is specified
- Note common 5e defaults (examples, not exhaustive):
  - Divine Smite: 2d8 at 1st-level slot, +1d8 per slot above 1st; +1d8 vs undead/fiends
  - Chromatic Orb: 3d8 at 1st-level slot, +1d8 per slot above 1st
  - Fireball: 8d6 at 3rd-level slot, +1d6 per slot above 3rd
  - Cure Wounds: 1d8 at 1st-level slot, +1d8 per slot above 1st (healing)
  - Longsword (1-handed): 1d8, Shortbow: 1d6, Greatsword: 2d6, Greataxe: 1d12
- If no dice are rolled for the primary effect, conclude that there is NO_DICE

Write a concise but comprehensive rationale referencing rules knowledge.

Action: {action}
"""

            analysis_response = await asyncio.to_thread(self.model.generate_content, analysis_prompt)
            analysis_text = (analysis_response.text or "").strip()

            # Step 2: Extract ONLY the dice notation (or NO_DICE) using the analysis
            extraction_prompt = f"""
From the analysis and action below, output ONLY ONE item:
- A single standard dice notation in XdY[+/-Z] form (e.g., 1d8, 2d6+3, 4d10-2)
OR
- The exact string NO_DICE if no dice are rolled for the primary effect.

Hard constraints:
- Output must be ONLY the dice notation or NO_DICE. No extra words, no code fences
- If multiple dice types exist, return the primary effect dice. Do not return compound expressions
- Assume base slot unless the action explicitly states a slot level

Action: {action}
Analysis:
{analysis_text}
"""

            extract_response = await asyncio.to_thread(self.model.generate_content, extraction_prompt)
            raw_output = (extract_response.text or "").strip()

            # Sanitize potential formatting
            cleaned = raw_output.replace("`", "").strip()
            cleaned = cleaned.splitlines()[0] if "\n" in cleaned else cleaned
            cleaned_lower = cleaned.lower().strip()

            if cleaned_lower == "no_dice" or cleaned_lower == "no dice":
                return None

            # Strict dice notation validation (single group with optional +/- modifier)
            simple_pattern = r"^\s*(\d+)d(\d+)([+-]\d+)?\s*$"
            match = re.match(simple_pattern, cleaned_lower)
            if not match:
                # Try to extract the first valid dice token if model added extras
                token_match = re.search(r"(\d+)d(\d+)([+-]\d+)?", cleaned_lower)
                if not token_match:
                    return None
                cleaned_lower = token_match.group(0)

            return cleaned_lower

        except Exception as e:
            print(f"Error parsing D&D action (two-step): {e}")
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


    @app_commands.command(name="dnd-help", description="Get D&D 5e guidance about rules, spells, or dice")
    @app_commands.describe(question="Ask a D&D question (e.g., 'How does Divine Smite scale?', 'What dice for Chromatic Orb at level 4?')")
    async def dnd_help(self, interaction: discord.Interaction, question: str):
        """Provide D&D 5e guidance using Gemini AI"""
        if not self.ai_enabled:
            await interaction.response.send_message(
                "❌ **AI Not Available:** Please configure a Gemini API key to use this command.",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            prompt = (
                "You are a concise, accurate D&D 5e rules assistant.\n"
                "Guidelines:\n"
                "- Answer clearly in 5e terms with brief bullet points when helpful.\n"
                "- Provide dice notation (e.g., 2d6+3) and short examples where useful.\n"
                "- Assume base rules. If slot level is unspecified, assume base slot.\n"
                "- If the answer varies by DM, note common rulings and typical options.\n"
                "- Only cite official sources by name when reasonably confident (no page numbers).\n"
                "- Keep it under ~300 words.\n\n"
                f"User question: {question}\n"
            )

            response = await asyncio.to_thread(self.model.generate_content, prompt)
            answer = (response.text or "").strip()

            if not answer:
                await interaction.followup.send(
                    "❌ I couldn't generate guidance right now. Please try again in a moment.",
                    ephemeral=True
                )
                return

            # Discord embed description max is 4096 characters
            if len(answer) > 4000:
                answer = answer[:3997] + "..."

            embed = discord.Embed(
                title="📖 D&D Help",
                description=answer,
                color=discord.Color.blurple()
            )
            embed.set_footer(text="Guidance only — your DM has final say • Powered by AI")

            await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(
                f"❌ **Error:** Unable to answer right now. Please try again later.\n\nDetails: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(DnDCog(bot))