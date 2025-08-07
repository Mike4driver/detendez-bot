import asyncio
import logging
import discord
from discord.ext import commands
from config import Config
from database import Database

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DetendezBot(commands.Bot):
    """Main bot class with initialization and event handling"""
    
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.voice_states = True
        intents.reactions = True
        
        super().__init__(
            command_prefix='!',  # Fallback prefix, mainly using slash commands
            intents=intents,
            help_command=None  # We'll implement our own help command
        )
        
        self.db = Database()
        
    async def setup_hook(self):
        """Initialize database and load cogs"""
        logger.info("Setting up bot...")
        
        # Initialize database
        await self.db.init_database()
        logger.info("Database initialized")
        
        # Load all cogs
        cogs_to_load = [
            'cogs.leveling',
            'cogs.starboard',
            'cogs.music',
            'cogs.birthday',
            'cogs.facts',
            'cogs.questions',
            'cogs.ai',
            'cogs.tts',
            'cogs.quotes',
            'cogs.help',
            'cogs.scheduler',
            'cogs.geographic',
            'cogs.dnd'
        ]
        
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded {cog}")
            except Exception as e:
                logger.error(f"Failed to load {cog}: {e}")
        
        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Event fired when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="for your messages | /help"
        )
        await self.change_presence(activity=activity)
    
    async def on_guild_join(self, guild):
        """Event fired when bot joins a new guild"""
        logger.info(f"Joined guild: {guild.name} (ID: {guild.id})")
        # Initialize guild configuration
        await self.db.create_default_guild_config(guild.id)
    
    async def on_member_remove(self, member):
        """Event fired when a member leaves a guild"""
        logger.info(f"Member left: {member.name} from {member.guild.name}")
        # Clean up user data
        await self.db.cleanup_user_data(member.id, member.guild.id)
    
    async def on_command_error(self, ctx, error):
        """Global error handler"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore unknown commands
        
        logger.error(f"Command error: {error}")
        
        if ctx.interaction:
            # For slash commands
            if not ctx.interaction.response.is_done():
                await ctx.interaction.response.send_message(
                    f"An error occurred: {str(error)}", ephemeral=True
                )
            else:
                await ctx.interaction.followup.send(
                    f"An error occurred: {str(error)}", ephemeral=True
                )
        else:
            # For regular commands
            await ctx.send(f"An error occurred: {str(error)}")

async def main():
    """Main function to run the bot"""
    # Validate configuration
    try:
        Config.validate_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return
    
    # Create and run bot
    bot = DetendezBot()
    
    try:
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.close()

if __name__ == "__main__":
    asyncio.run(main()) 