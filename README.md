# DetendezBot 🤖

A comprehensive multi-feature Discord bot with leveling, starboard, music, birthdays, AI-powered content, D&D tools, geographic polls, quotes, scheduling, TTS, and more — built with Python and discord.py.

## ✨ Features

### 📊 Leveling System
- **XP Tracking**: Configurable XP per message and cooldown (default: 15 XP per message, 60s cooldown)
- **Leaderboards**: Server rankings with medals for top 3
- **Level-up Notifications**: Automatic announcements with user avatars
- **Admin Controls**: Set levels, add/remove XP, reset users, configure settings
- **XP Formula**: 5 × (level²) + 50 × level + 100

### ⭐ Starboard
- **Highlight Great Messages**: Auto-feature messages by star reactions
- **Live Updates**: Star counts update dynamically with reactions
- **Smart Rules**: Prevent self-starring, handle message deletions, remove below threshold
- **Manual Starring**: `/star <message_id>` command for moderators
- **Configurable**: Custom emoji, threshold (default: 3), dedicated channel

### 🎵 Music Bot
- **YouTube Playback**: Direct URLs or search queries with yt-dlp
- **Full Queue Management**: Add, remove, view queue, skip, stop
- **Playback Controls**: Pause/resume, volume control (0-100%)
- **Auto-Management**: Queue progression, 5-minute inactivity disconnect
- **Cookie Support**: Upload cookies for better YouTube reliability
- **Voice Channel Reconnection**: Robust connection handling with retries

### 🎂 Birthday System
- **Flexible Date Input**: MM/DD or "Month Day" formats (e.g., "July 21")
- **Daily Announcements**: Automatic celebrations with user avatars
- **Birthday Role**: Optional role assignment on birthday
- **Permanent Birthday Post**: Auto-updating message listing all birthdays by month
- **Birthday Commands**: View individual birthdays, monthly lists, or all chronologically
- **Smart Validation**: Prevents invalid dates (e.g., February 30)

### 🗺️ Geographic Polls
- **US Region Polls**: React with emojis for West Coast 🌊, East Coast 🏙️, North 🏔️, South 🌵
- **Single Selection**: Auto-removes previous reactions when selecting new region
- **Results Tracking**: View counts and percentages per region
- **User History**: Check your past geographic selections
- **Custom Titles**: Create polls with custom descriptions

### 🧠 AI-Powered Content (Gemini)
- **Daily Facts**: Auto-generated educational facts with 16 different prompt categories
- **Daily Questions**: Thought-provoking discussion questions with auto-reactions
- **Interactive Chat**: `/ask` command for custom AI queries
- **Repetition Avoidance**: Tracks recent content to prevent duplicates
- **Fallback Content**: Curated facts/questions when AI is unavailable
- **Content Variety**: Science, history, philosophy, creativity, and more

### 🧙 D&D Tools
- **Dice Rolling**: Standard notation (1d20, 2d6+3, 4d8-2) with critical hit detection
- **Action Parsing**: AI-powered parsing of D&D actions ("level 3 smite", "chromatic orb level 4")
- **Rule Guidance**: `/dnd-help` for concise 5e rules assistance
- **Smart Recognition**: Handles spell scaling, class features, weapon attacks
- **Visual Feedback**: Special colors for natural 20s/1s and high damage rolls

### 🗓️ Smart Scheduling
- **Natural Language**: Create Discord events from phrases like "Team meeting Friday 3 PM"
- **Timezone Support**: Specify timezone or defaults to UTC
- **Calendar Integration**: Google Calendar links and ICS file attachments
- **Auto-Parsing**: AI extracts title, time, location, and description
- **Discord Events**: Creates proper Discord Scheduled Events

### 🎨 Quote Generator
- **Visual Quotes**: Generate colorful quote images with decorative elements
- **Member Attribution**: Quote with Discord member mentions or custom names
- **Random Styling**: 10 color schemes with emoji decorations and shadows
- **Font Handling**: Cross-platform font support with fallbacks
- **Text Wrapping**: Smart text fitting with validation (500 char limit)

### 🎤 Text-to-Speech (ElevenLabs)
- **High-Quality Voices**: Multiple AI voices with voice browsing
- **Model Selection**: Multilingual, Flash (fast), and Turbo models
- **Voice Playback**: Optional playback in your current voice channel
- **Streaming TTS**: Real-time audio generation for lower latency
- **Voice Management**: List available voices with IDs and names
- **Length Controls**: Configurable character limits (default: 500)

### ⚙️ Configuration & Admin
- **Role-Based Access**: Configurable admin role beyond server administrators
- **Per-Server Settings**: All features independently configurable per guild
- **Database Migrations**: Safe automatic schema updates
- **Permission Validation**: Checks bot permissions before configuration
- **Comprehensive Help**: `/help` system with category-specific guidance
- **SQLite Storage**: Reliable data persistence with cleanup routines

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Discord Bot Token
- (Optional) Google Gemini API Key
- (Optional) ElevenLabs API Key
- (Optional) YouTube cookies file

### Installation

1) Clone and enter the repo
```bash
git clone <repository-url>
cd detendezbot
```

2) Install dependencies
```bash
pip install -r requirements.txt
```

3) Configure environment
Create a `.env` file in the project root:
```env
DISCORD_TOKEN=your_discord_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
LOG_LEVEL=INFO
```

4) Run the bot
```bash
python main.py
```

### Discord Bot Setup
1) Create an application/bot in the Discord Developer Portal and copy the token

2) Generate an invite with scopes `bot` and `applications.commands`, permissions:
- Send Messages, Read Message History, Add Reactions, Use Slash Commands
- Connect, Speak (music)
- Manage Roles (birthday role)
- Embed Links, Attach Files
- Manage Events (scheduling)

3) Invite the bot to your server

### Optional: Gemini AI Setup
- Get an API key from Google AI Studio and set `GEMINI_API_KEY`
- Without it: facts/questions fall back; AI-only commands (e.g., `/ask`, parts of D&D) are limited

### Optional: ElevenLabs TTS Setup
- Get an API key from ElevenLabs and set `ELEVENLABS_API_KEY`

## 📖 Usage Guide

### User Commands
- `/help [category]` — Show help (specific category optional)
- `/rank [user]`, `/leaderboard [limit]` — Leveling system
- Music: `/play <query>`, `/queue`, `/skip`, `/stop`, `/pause`, `/resume`, `/volume <0-100>`, `/nowplaying`, `/remove <pos>`
- AI Content: `/fact`, `/question`, `/ask <question>`
- TTS: `/tts <text> [voice] [model] [play_in_voice]`, `/voices`, `/tts-models`, `/tts-stream`
- Birthdays: `/setbirthday <date>`, `/birthday [user]`, `/birthdays [month]`, `/removebirthday`, `/allbirthdays`
- Starboard: `/starboard`, `/star <message_id>`
- Geographic: `/geographic-poll [title] [description]`, `/geographic-results <message_id>`, `/my-region`
- D&D: `/roll <XdY[+/-Z]>`, `/dnd-action <action>`, `/dnd-help <question>`
- Scheduling: `/schedule <prompt> [timezone]`
- Quotes: `/quote <text> <@author>`, `/quote-text <text> <author_name>`

### Admin Commands (Administrator or Admin Role)
- General: `/admin-role <role>` — Set admin role for bot commands
- Leveling: `/leveling-config [xp_per_message] [cooldown] [level_up_channel]`, `/setlevel <user> <level>`, `/addxp <user> <amount>`, `/removexp <user> <amount>`, `/resetxp [user]`
- Starboard: `/starboard-config [channel] [emoji] [threshold]`
- Birthdays: `/birthday-config [channel] [role] [permanent_channel]`, `/refresh-birthday-post`
- Facts & Questions: `/fact-config [channel] [time]`, `/question-config [channel] [time]`
- TTS: `/tts-config [max_length] [default_voice] [default_model]`
- Music cookies: `/set_cookies [cookies] [attachment]`, `/refresh_cookies`, `/cookie_status`

### Configuration Examples
- Leveling:
```bash
/leveling-config xp_per_message:20 cooldown:30 level_up_channel:#level-ups
```
- Starboard:
```bash
/starboard-config channel:#starboard threshold:5 emoji:⭐
```
- Birthdays (with permanent post):
```bash
/birthday-config channel:#birthdays role:@Birthday permanent_channel:#birthday-list
```
- Facts & Questions:
```bash
/fact-config channel:#daily-facts time:09:00
/question-config channel:#daily-questions time:15:00
```
- TTS:
```bash
/tts-config max_length:1000 default_voice:Rachel
```

## 🛠️ Development

### Project Structure
```
detendezbot/
├── main.py            # Bot entry point
├── config.py          # Configuration management
├── database.py        # Database operations (with safe migrations)
├── requirements.txt   # Python dependencies
├── cogs/              # Feature modules
│   ├── leveling.py    # XP and leveling
│   ├── starboard.py   # Starboard
│   ├── music.py       # Music playback
│   ├── birthday.py    # Birthdays (incl. permanent post)
│   ├── facts.py       # Daily facts
│   ├── questions.py   # Daily questions
│   ├── ai.py          # Interactive AI chat
│   ├── tts.py         # Text-to-speech
│   ├── geographic.py  # Geographic reaction polls
│   ├── quotes.py      # Quote image generator
│   ├── scheduler.py   # Smart scheduling
│   ├── dnd.py         # D&D tools (dice, action parser, help)
│   └── help.py        # Help system
├── tests/             # Test files
└── README.md
```

### Database Schema
SQLite tables include:
- `user_levels`, `starboard_messages`, `user_birthdays`, `guild_config`
- `recent_content`, `music_queue`, `geographic_polls`, `geographic_selections`

### Adding New Features
1) Create a new cog in `cogs/`
2) Follow existing patterns for DB access and error handling
3) Add the cog to the load list in `main.py`
4) Update this README and the help system if needed

## 🔧 Configuration Options

### Environment Variables
- `DISCORD_TOKEN` — Discord bot token (required)
- `GEMINI_API_KEY` — Google Gemini API key (optional)
- `ELEVENLABS_API_KEY` — ElevenLabs API key (optional)
- `LOG_LEVEL` — INFO, DEBUG, WARNING, ERROR

### Per-Server Settings
Configurable via slash commands for leveling, starboard, birthdays (incl. permanent post), facts, questions, TTS, and more.

## 🐛 Troubleshooting

1) Bot not responding — verify permissions, token, and command sync (restart)
2) Music issues — check voice perms, yt-dlp, and cookies
3) AI not working — set `GEMINI_API_KEY`, check quota
4) TTS not working — set `ELEVENLABS_API_KEY`, check limits
5) Database errors — ensure write permissions; restarting runs migrations

### Logging
Logs to console and `bot.log`. Review logs for details.

## 📝 License
Open source. Modify and distribute as needed.

## 🤝 Contributing
PRs and issues welcome for bugs and features.

## 📞 Support
Open an issue for support or questions.

---
Note: Your DM has final say on D&D rulings. Use responsibly within Discord's terms.