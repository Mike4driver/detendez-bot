import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import random
import os
from typing import Optional

class QuotesCog(commands.Cog):
    """Quote generation functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.quote_backgrounds = [
            (135, 206, 235),  # Sky blue
            (255, 182, 193),  # Light pink
            (144, 238, 144),  # Light green
            (255, 215, 0),    # Gold
            (221, 160, 221),  # Plum
            (255, 165, 0),    # Orange
            (176, 224, 230),  # Powder blue
            (255, 218, 185),  # Peach
            (230, 230, 250),  # Lavender
            (255, 240, 245),  # Lavender blush
        ]
        
        self.funny_elements = [
            "✨", "🎭", "🎪", "🎨", "🌟", "💫", "🎬", "📸", "🎯", "🎲",
            "🌈", "🎊", "🎉", "🎈", "🎭", "🎪", "🎨", "🎵", "🎶", "🎸"
        ]
        
    def _get_font_path(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Get system font or fallback to default"""
        try:
            # Try to use system fonts (works on most systems)
            font_paths = [
                "arial.ttf",
                "Arial.ttf", 
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux
                "C:/Windows/Fonts/arial.ttf",  # Windows
                "C:/Windows/Fonts/calibri.ttf",  # Windows alternative
            ]
            
            if bold:
                bold_paths = [
                    "arialbd.ttf",
                    "Arial-Bold.ttf",
                    "/System/Library/Fonts/Arial-Bold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "C:/Windows/Fonts/arialbd.ttf",
                    "C:/Windows/Fonts/calibrib.ttf",
                ]
                font_paths = bold_paths + font_paths
            
            for font_path in font_paths:
                try:
                    return ImageFont.truetype(font_path, size)
                except (OSError, IOError):
                    continue
                    
            # Fallback to default font
            return ImageFont.load_default()
            
        except Exception:
            return ImageFont.load_default()
    
    def _wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
        """Wrap text to fit within the specified width"""
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
            
            if text_width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Word is too long, force break it
                    lines.append(word)
                    current_line = ""
        
        if current_line:
            lines.append(current_line)
            
        return lines
    
    def _generate_quote_image(self, quote_text: str, author_name: str) -> io.BytesIO:
        """Generate a funny quote image"""
        # Image dimensions
        width, height = 800, 600
        
        # Create image with random background color
        bg_color = random.choice(self.quote_backgrounds)
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # Add some decorative elements
        decorations = random.sample(self.funny_elements, k=random.randint(3, 6))
        
        # Draw decorative elements in corners
        decoration_font = self._get_font_path(40)
        positions = [
            (50, 50), (width-100, 50), (50, height-100), (width-100, height-100),
            (width//2-20, 50), (width//2-20, height-100)
        ]
        
        for i, decoration in enumerate(decorations):
            if i < len(positions):
                pos = positions[i]
                draw.text(pos, decoration, fill=(255, 255, 255, 128), font=decoration_font)
        
        # Main quote text
        quote_font = self._get_font_path(32)
        max_quote_width = width - 120
        quote_lines = self._wrap_text(f'"{quote_text}"', quote_font, max_quote_width)
        
        # Calculate total height of quote text
        line_height = 40
        total_quote_height = len(quote_lines) * line_height
        
        # Center the quote vertically
        start_y = (height - total_quote_height - 80) // 2  # 80 for author space
        
        # Draw quote text with shadow effect
        shadow_offset = 2
        for i, line in enumerate(quote_lines):
            y_pos = start_y + i * line_height
            
            # Draw shadow
            draw.text((62 + shadow_offset, y_pos + shadow_offset), line, 
                     fill=(0, 0, 0, 64), font=quote_font)
            
            # Draw main text
            draw.text((60, y_pos), line, fill=(50, 50, 50), font=quote_font)
        
        # Author attribution
        author_font = self._get_font_path(24, bold=True)
        author_text = f"— {author_name}"
        
        # Position author text
        author_y = start_y + total_quote_height + 20
        
        # Draw author with shadow
        draw.text((62 + shadow_offset, author_y + shadow_offset), author_text, 
                 fill=(0, 0, 0, 64), font=author_font)
        draw.text((60, author_y), author_text, fill=(80, 80, 80), font=author_font)
        
        # Add a subtle border
        border_color = tuple(max(0, c - 40) for c in bg_color)
        draw.rectangle([10, 10, width-10, height-10], outline=border_color, width=3)
        
        # Convert to BytesIO
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        
        return img_bytes
    
    @app_commands.command(name="quote", description="Generate a funny quote image")
    @app_commands.describe(
        quote="The quote text to put on the image",
        author="The person who said the quote (mention them with @)"
    )
    async def generate_quote(
        self, 
        interaction: discord.Interaction, 
        quote: str, 
        author: discord.Member
    ):
        """Generate and post a quote image"""
        await interaction.response.defer()
        
        try:
            # Validate input
            if len(quote) > 500:
                await interaction.followup.send(
                    "❌ Quote is too long! Please keep it under 500 characters.",
                    ephemeral=True
                )
                return
            
            if len(quote.strip()) == 0:
                await interaction.followup.send(
                    "❌ Quote cannot be empty!",
                    ephemeral=True
                )
                return
            
            # Generate the quote image
            author_name = author.display_name
            img_bytes = self._generate_quote_image(quote, author_name)
            
            # Create Discord file
            file = discord.File(img_bytes, filename=f"quote_{author.id}.png")
            
            # Create embed
            embed = discord.Embed(
                title="📜 Quote Generated!",
                description=f"Quote by {author.mention}",
                color=discord.Color.from_rgb(135, 206, 235),
                timestamp=interaction.created_at
            )
            embed.set_image(url=f"attachment://quote_{author.id}.png")
            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            # Send the quote
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ An error occurred while generating the quote: {str(e)}",
                ephemeral=True
            )
    
    @app_commands.command(name="quote-text", description="Generate a quote with custom author name")
    @app_commands.describe(
        quote="The quote text to put on the image",
        author_name="The name of the person who said the quote (as text)"
    )
    async def generate_quote_text(
        self, 
        interaction: discord.Interaction, 
        quote: str, 
        author_name: str
    ):
        """Generate and post a quote image with custom author name"""
        await interaction.response.defer()
        
        try:
            # Validate input
            if len(quote) > 500:
                await interaction.followup.send(
                    "❌ Quote is too long! Please keep it under 500 characters.",
                    ephemeral=True
                )
                return
            
            if len(quote.strip()) == 0:
                await interaction.followup.send(
                    "❌ Quote cannot be empty!",
                    ephemeral=True
                )
                return
                
            if len(author_name.strip()) == 0:
                await interaction.followup.send(
                    "❌ Author name cannot be empty!",
                    ephemeral=True
                )
                return
            
            if len(author_name) > 50:
                await interaction.followup.send(
                    "❌ Author name is too long! Please keep it under 50 characters.",
                    ephemeral=True
                )
                return
            
            # Generate the quote image
            img_bytes = self._generate_quote_image(quote, author_name.strip())
            
            # Create Discord file
            file = discord.File(img_bytes, filename="quote.png")
            
            # Create embed
            embed = discord.Embed(
                title="📜 Quote Generated!",
                description=f"Quote by **{author_name.strip()}**",
                color=discord.Color.from_rgb(135, 206, 235),
                timestamp=interaction.created_at
            )
            embed.set_image(url="attachment://quote.png")
            embed.set_footer(
                text=f"Requested by {interaction.user.display_name}",
                icon_url=interaction.user.display_avatar.url
            )
            
            # Send the quote
            await interaction.followup.send(embed=embed, file=file)
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ An error occurred while generating the quote: {str(e)}",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(QuotesCog(bot)) 