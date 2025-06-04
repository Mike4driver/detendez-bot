#!/usr/bin/env python3
"""
Quick start script for DetendezBot
This script checks for required dependencies and environment setup
"""

import sys
import os

def check_requirements():
    """Check if all required packages are installed"""
    required_packages = [
        'discord.py', 'aiosqlite', 'yt-dlp', 'PyNaCl', 
        'python-dotenv', 'aiohttp', 'google-generativeai'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install with: pip install -r requirements.txt")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists and has required variables"""
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("📝 Create a .env file with your Discord bot token:")
        print("   DISCORD_TOKEN=your_discord_bot_token_here")
        print("   GEMINI_API_KEY=your_gemini_api_key_here  # Optional")
        return False
    
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv('DISCORD_TOKEN'):
        print("❌ DISCORD_TOKEN not found in .env file!")
        print("📝 Add your Discord bot token to the .env file")
        return False
    
    print("✅ Environment file configured")
    
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️  GEMINI_API_KEY not found - AI features will use fallback content")
    else:
        print("✅ Gemini AI configured")
    
    return True

def main():
    """Main startup function"""
    print("🤖 DetendezBot Startup Check")
    print("=" * 30)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(f"   Current version: {sys.version}")
        return
    
    print(f"✅ Python version: {sys.version.split()[0]}")
    
    # Check requirements
    if not check_requirements():
        return
    
    print("✅ All packages installed")
    
    # Check environment
    if not check_env_file():
        return
    
    print("\n🚀 Starting DetendezBot...")
    print("=" * 30)
    
    # Import and run the main bot
    try:
        from main import main as bot_main
        import asyncio
        asyncio.run(bot_main())
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        print("📋 Check the logs for more information")

if __name__ == "__main__":
    main() 