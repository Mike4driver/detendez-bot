#!/usr/bin/env python3
"""
Setup script for DetendezBot
Helps users configure the bot for first-time use
"""

import os
import sys

def create_env_file():
    """Create .env file with user input"""
    print("🔧 Setting up environment configuration...")
    print()
    
    # Get Discord token
    print("📋 Discord Bot Setup:")
    print("1. Go to https://discord.com/developers/applications")
    print("2. Create a new application or select existing one")
    print("3. Go to 'Bot' section and copy the token")
    print()
    
    token = input("Enter your Discord bot token: ").strip()
    if not token:
        print("❌ Bot token is required!")
        return False
    
    # Get optional Gemini API key
    print()
    print("🤖 AI Features Setup (Optional):")
    print("For AI-generated facts and questions:")
    print("1. Go to https://makersuite.google.com/app/apikey")
    print("2. Create a new API key")
    print("3. Enter it below (or press Enter to skip)")
    print()
    
    gemini_key = input("Enter your Gemini API key (optional): ").strip()
    
    # Create .env file
    env_content = f"""# Discord Bot Configuration
DISCORD_TOKEN={token}

# Optional: Google Gemini AI API Key for facts and questions features
# Get your API key from: https://makersuite.google.com/app/apikey
{f'GEMINI_API_KEY={gemini_key}' if gemini_key else '# GEMINI_API_KEY=your_gemini_api_key_here'}

# Logging Configuration (optional)
# Options: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
"""
    
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        print("✅ .env file created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")
        return False

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    
    try:
        import subprocess
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Dependencies installed successfully!")
            return True
        else:
            print(f"❌ Error installing dependencies: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def show_next_steps():
    """Show next steps for the user"""
    print("\n🎉 Setup complete!")
    print("=" * 40)
    print()
    print("📋 Next steps:")
    print("1. Invite your bot to a Discord server:")
    print("   • Go to Discord Developer Portal")
    print("   • OAuth2 → URL Generator")
    print("   • Select 'bot' and 'applications.commands'")
    print("   • Select required permissions (see README)")
    print("   • Use generated URL to invite bot")
    print()
    print("2. Start the bot:")
    print("   python main.py")
    print("   or")
    print("   python run.py")
    print()
    print("3. Configure the bot in your server:")
    print("   Use /help to see all available commands")
    print("   Use admin commands to configure features")
    print()
    print("📖 For detailed instructions, see README.md")

def main():
    """Main setup function"""
    print("🤖 DetendezBot Setup Wizard")
    print("=" * 30)
    print()
    
    # Check if .env already exists
    if os.path.exists('.env'):
        print("⚠️  .env file already exists!")
        response = input("Do you want to recreate it? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("Setup cancelled.")
            return
    
    # Check if requirements.txt exists
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found!")
        print("Make sure you're in the correct directory.")
        return
    
    # Install dependencies
    response = input("Install dependencies from requirements.txt? (Y/n): ").strip().lower()
    if response not in ['n', 'no']:
        if not install_dependencies():
            print("❌ Setup failed during dependency installation.")
            return
    
    print()
    
    # Create environment file
    if not create_env_file():
        print("❌ Setup failed during environment configuration.")
        return
    
    print()
    show_next_steps()

if __name__ == "__main__":
    main() 