import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import google.generativeai as genai
from config import Config
from datetime import datetime

class AICog(commands.Cog):
    """Interactive AI prompt command"""

    def __init__(self, bot):
        self.bot = bot
        self.setup_ai()

    def setup_ai(self):
        """Setup Gemini AI"""
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-lite-001')
            self.ai_enabled = True
        else:
            self.model = None
            self.ai_enabled = False

    @app_commands.command(name="ask", description="Ask the AI any question")
    @app_commands.describe(question="Your prompt to the AI")
    async def ask(self, interaction: discord.Interaction, question: str):
        """Ask a custom question to the AI"""
        await interaction.response.defer()
        if not self.ai_enabled:
            await interaction.followup.send(
                "❌ AI is disabled because no API key is configured.",
                ephemeral=True
            )
            return
        try:
            question = f"Answer the question in a short and concise manner (max 1900 characters). The question is: {question}"
            response = await asyncio.to_thread(self.model.generate_content, question)
            answer = response.text.strip()
            # Truncate if too long for Discord embed
            if len(answer) > 1900:
                answer = answer[:1897] + "..."

            embed = discord.Embed(
                title="💬 AI Response",
                description=answer,
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            embed.set_footer(text="Powered by AI")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error querying AI: {e}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(AICog(bot)) 