import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuration class for the Discord bot"""
    
    # Discord Bot Configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
    
    # Database Configuration
    DATABASE_FILE = 'bot_data.db'
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Leveling System Defaults
    DEFAULT_XP_PER_MESSAGE = 15
    DEFAULT_XP_COOLDOWN = 60  # seconds
    
    # Starboard Defaults
    DEFAULT_STAR_THRESHOLD = 3
    DEFAULT_STAR_EMOJI = '⭐'
    
    # Music Bot Defaults
    DEFAULT_VOLUME = 50
    INACTIVITY_TIMEOUT = 300  # 5 minutes
    
    # Birthday Bot Defaults
    DEFAULT_BIRTHDAY_TIME = '00:00'  # midnight
    
    # Fact/Question Bot Defaults
    DEFAULT_FACT_TIME = '09:00'  # 9 AM
    DEFAULT_QUESTION_TIME = '15:00'  # 3 PM
    
    # Spotify API Credentials (optional)
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
    
    # TTS Defaults
    DEFAULT_TTS_VOICE = "Rachel"  # Default ElevenLabs voice
    MAX_TTS_LENGTH = 500  # Maximum characters for TTS
    
    @classmethod
    def validate_config(cls):
        """Validate that required configuration is present"""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required")
        
        if not cls.GEMINI_API_KEY:
            print("Warning: GEMINI_API_KEY not set. Fact/Question features will be disabled.")
        
        if not cls.ELEVENLABS_API_KEY:
            print("Warning: ELEVENLABS_API_KEY not set. Text-to-speech features will be disabled.")
        
        # Warn if Spotify credentials are missing
        if not (cls.SPOTIFY_CLIENT_ID and cls.SPOTIFY_CLIENT_SECRET):
            print("Warning: Spotify credentials not set. Spotify support will be disabled.")
        
        return True 