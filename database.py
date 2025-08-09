import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any
from config import Config

class Database:
    """Database management class for the Discord bot"""
    
    def __init__(self, db_file: str = None):
        self.db_file = db_file or Config.DATABASE_FILE
    
    async def init_database(self):
        """Initialize the database with required tables"""
        async with aiosqlite.connect(self.db_file) as db:
            # Leveling System Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_levels (
                    user_id INTEGER,
                    guild_id INTEGER,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_message TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Starboard Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS starboard_messages (
                    original_message_id INTEGER,
                    starboard_message_id INTEGER,
                    guild_id INTEGER,
                    star_count INTEGER DEFAULT 0,
                    PRIMARY KEY (original_message_id, guild_id)
                )
            ''')
            
            # Birthday Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_birthdays (
                    user_id INTEGER,
                    guild_id INTEGER,
                    birth_month INTEGER,
                    birth_day INTEGER,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')
            
            # Guild Configuration Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS guild_config (
                    guild_id INTEGER PRIMARY KEY,
                    -- Leveling Config
                    xp_per_message INTEGER DEFAULT 15,
                    xp_cooldown INTEGER DEFAULT 60,
                    level_up_channel INTEGER,
                    excluded_channels TEXT,
                    -- Starboard Config
                    starboard_channel INTEGER,
                    star_threshold INTEGER DEFAULT 3,
                    star_emoji TEXT DEFAULT '⭐',
                    -- Birthday Config
                    birthday_channel INTEGER,
                    birthday_role INTEGER,
                    birthday_time TEXT DEFAULT '00:00',
                    birthday_permanent_channel INTEGER,
                    birthday_permanent_message INTEGER,
                    admin_role INTEGER,
                    -- Fact/Question Config
                    fact_channel INTEGER,
                    fact_time TEXT DEFAULT '09:00',
                    question_channel INTEGER,
                    question_time TEXT DEFAULT '15:00'
                )
            ''')
            
            # Music Queue Table (in-memory alternative could be used)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS music_queue (
                    guild_id INTEGER,
                    position INTEGER,
                    title TEXT,
                    url TEXT,
                    duration INTEGER,
                    requested_by INTEGER,
                    PRIMARY KEY (guild_id, position)
                )
            ''')
            
            # Recently Posted Content (to avoid repetition)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS recent_content (
                    guild_id INTEGER,
                    content_type TEXT,
                    content TEXT,
                    posted_date DATE DEFAULT CURRENT_DATE,
                    PRIMARY KEY (guild_id, content_type, content)
                )
            ''')
            
            # Geographic Polls Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS geographic_polls (
                    message_id INTEGER,
                    guild_id INTEGER,
                    channel_id INTEGER,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (message_id, guild_id)
                )
            ''')
            
            # Geographic Selections Table
            await db.execute('''
                CREATE TABLE IF NOT EXISTS geographic_selections (
                    user_id INTEGER,
                    message_id INTEGER,
                    guild_id INTEGER,
                    region TEXT,
                    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, message_id, guild_id)
                )
            ''')
            
            # Run migrations for existing databases
            await self._run_migrations(db)
            
            await db.commit()
    
    async def _run_migrations(self, db):
        """Run database migrations for existing databases"""
        # Check if birthday permanent columns exist
        try:
            await db.execute('SELECT birthday_permanent_channel FROM guild_config LIMIT 1')
        except Exception:
            # Columns don't exist, add them
            print("Running migration: Adding birthday permanent post columns...")
            await db.execute('ALTER TABLE guild_config ADD COLUMN birthday_permanent_channel INTEGER')
            await db.execute('ALTER TABLE guild_config ADD COLUMN birthday_permanent_message INTEGER')
            print("Migration completed: Birthday permanent post columns added")
        # Add admin_role column if missing
        try:
            await db.execute('SELECT admin_role FROM guild_config LIMIT 1')
        except Exception:
            print("Running migration: Adding admin_role column...")
            await db.execute('ALTER TABLE guild_config ADD COLUMN admin_role INTEGER')
            print("Migration completed: admin_role column added")
    
    # Leveling System Methods
    async def get_user_level_data(self, user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get user's level data"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT xp, level, last_message FROM user_levels WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {'xp': row[0], 'level': row[1], 'last_message': row[2]}
                return None
    
    async def update_user_xp(self, user_id: int, guild_id: int, xp_to_add: int):
        """Update user's XP and level"""
        async with aiosqlite.connect(self.db_file) as db:
            # Insert or update user data
            await db.execute('''
                INSERT INTO user_levels (user_id, guild_id, xp, level, last_message)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET 
                    xp = xp + ?,
                    last_message = CURRENT_TIMESTAMP
            ''', (user_id, guild_id, xp_to_add, xp_to_add))
            
            # Get updated XP and calculate new level
            async with db.execute(
                'SELECT xp FROM user_levels WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            ) as cursor:
                result = await cursor.fetchone()
                if result:
                    current_xp = result[0]
                    new_level = self.calculate_level_from_xp(current_xp)
                    
                    await db.execute(
                        'UPDATE user_levels SET level = ? WHERE user_id = ? AND guild_id = ?',
                        (new_level, user_id, guild_id)
                    )
            
            await db.commit()
    
    async def get_leaderboard(self, guild_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get server leaderboard"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('''
                SELECT user_id, xp, level,
                       ROW_NUMBER() OVER (ORDER BY xp DESC) as rank
                FROM user_levels 
                WHERE guild_id = ? 
                ORDER BY xp DESC 
                LIMIT ?
            ''', (guild_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {'user_id': row[0], 'xp': row[1], 'level': row[2], 'rank': row[3]}
                    for row in rows
                ]
    
    async def set_user_level(self, user_id: int, guild_id: int, level: int):
        """Manually set user's level"""
        xp_required = self.calculate_xp_for_level(level)
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT INTO user_levels (user_id, guild_id, xp, level)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET 
                    xp = ?, level = ?
            ''', (user_id, guild_id, xp_required, level, xp_required, level))
            await db.commit()
    
    # Starboard Methods
    async def add_starboard_message(self, original_id: int, starboard_id: int, guild_id: int, star_count: int):
        """Add a message to starboard tracking"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT INTO starboard_messages (original_message_id, starboard_message_id, guild_id, star_count)
                VALUES (?, ?, ?, ?)
            ''', (original_id, starboard_id, guild_id, star_count))
            await db.commit()
    
    async def get_starboard_message(self, original_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get starboard message data"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT starboard_message_id, star_count FROM starboard_messages WHERE original_message_id = ? AND guild_id = ?',
                (original_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {'starboard_message_id': row[0], 'star_count': row[1]}
                return None
    
    async def update_starboard_count(self, original_id: int, guild_id: int, star_count: int):
        """Update star count for a starboard message"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                'UPDATE starboard_messages SET star_count = ? WHERE original_message_id = ? AND guild_id = ?',
                (star_count, original_id, guild_id)
            )
            await db.commit()
    
    async def remove_starboard_message(self, original_id: int, guild_id: int):
        """Remove a message from starboard tracking"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                'DELETE FROM starboard_messages WHERE original_message_id = ? AND guild_id = ?',
                (original_id, guild_id)
            )
            await db.commit()
    
    # Birthday Methods
    async def set_user_birthday(self, user_id: int, guild_id: int, month: int, day: int):
        """Set user's birthday"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT INTO user_birthdays (user_id, guild_id, birth_month, birth_day)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, guild_id) DO UPDATE SET 
                    birth_month = ?, birth_day = ?
            ''', (user_id, guild_id, month, day, month, day))
            await db.commit()
    
    async def get_birthdays_for_date(self, guild_id: int, month: int, day: int) -> List[int]:
        """Get users with birthdays on specific date"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT user_id FROM user_birthdays WHERE guild_id = ? AND birth_month = ? AND birth_day = ?',
                (guild_id, month, day)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    async def get_birthdays_for_month(self, guild_id: int, month: int) -> List[Dict[str, Any]]:
        """Get all birthdays for a specific month"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT user_id, birth_day FROM user_birthdays WHERE guild_id = ? AND birth_month = ? ORDER BY birth_day',
                (guild_id, month)
            ) as cursor:
                rows = await cursor.fetchall()
                return [{'user_id': row[0], 'day': row[1]} for row in rows]
    
    # Guild Configuration Methods
    async def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        """Get guild configuration"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT * FROM guild_config WHERE guild_id = ?',
                (guild_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                else:
                    # Create default config
                    await self.create_default_guild_config(guild_id)
                    return await self.get_guild_config(guild_id)
    
    async def create_default_guild_config(self, guild_id: int):
        """Create default configuration for a guild"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                'INSERT OR IGNORE INTO guild_config (guild_id) VALUES (?)',
                (guild_id,)
            )
            await db.commit()
    
    async def update_guild_config(self, guild_id: int, **kwargs):
        """Update guild configuration"""
        if not kwargs:
            return
        
        set_clause = ', '.join([f'{key} = ?' for key in kwargs.keys()])
        values = list(kwargs.values()) + [guild_id]
        
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                f'UPDATE guild_config SET {set_clause} WHERE guild_id = ?',
                values
            )
            await db.commit()
    
    # Cleanup Methods
    async def cleanup_user_data(self, user_id: int, guild_id: int):
        """Remove all user data when they leave the server"""
        async with aiosqlite.connect(self.db_file) as db:
            # Remove from leveling
            await db.execute(
                'DELETE FROM user_levels WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            )
            
            # Remove birthday
            await db.execute(
                'DELETE FROM user_birthdays WHERE user_id = ? AND guild_id = ?',
                (user_id, guild_id)
            )
            
            await db.commit()
    
    # Geographic Poll Methods
    async def add_geographic_poll(self, message_id: int, guild_id: int, title: str, channel_id: int = None):
        """Add a geographic poll to tracking"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT INTO geographic_polls (message_id, guild_id, channel_id, title)
                VALUES (?, ?, ?, ?)
            ''', (message_id, guild_id, channel_id, title))
            await db.commit()
    
    async def is_geographic_poll(self, message_id: int, guild_id: int) -> bool:
        """Check if a message is a geographic poll"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT 1 FROM geographic_polls WHERE message_id = ? AND guild_id = ?',
                (message_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row is not None
    
    async def get_geographic_poll(self, message_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get geographic poll data"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT title, channel_id, created_at FROM geographic_polls WHERE message_id = ? AND guild_id = ?',
                (message_id, guild_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {'title': row[0], 'channel_id': row[1], 'created_at': row[2]}
                return None
    
    async def add_geographic_selection(self, user_id: int, message_id: int, guild_id: int, region: str):
        """Add a user's geographic selection"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute('''
                INSERT OR REPLACE INTO geographic_selections (user_id, message_id, guild_id, region)
                VALUES (?, ?, ?, ?)
            ''', (user_id, message_id, guild_id, region))
            await db.commit()
    
    async def remove_geographic_selection(self, user_id: int, message_id: int, guild_id: int, region: str = None):
        """Remove a user's geographic selection"""
        async with aiosqlite.connect(self.db_file) as db:
            if region:
                await db.execute(
                    'DELETE FROM geographic_selections WHERE user_id = ? AND message_id = ? AND guild_id = ? AND region = ?',
                    (user_id, message_id, guild_id, region)
                )
            else:
                await db.execute(
                    'DELETE FROM geographic_selections WHERE user_id = ? AND message_id = ? AND guild_id = ?',
                    (user_id, message_id, guild_id)
                )
            await db.commit()
    
    async def remove_user_geographic_selection(self, user_id: int, message_id: int, guild_id: int):
        """Remove all geographic selections for a user on a specific poll"""
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(
                'DELETE FROM geographic_selections WHERE user_id = ? AND message_id = ? AND guild_id = ?',
                (user_id, message_id, guild_id)
            )
            await db.commit()
    
    async def get_geographic_results(self, message_id: int, guild_id: int) -> Dict[str, int]:
        """Get geographic poll results"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute(
                'SELECT region, COUNT(*) FROM geographic_selections WHERE message_id = ? AND guild_id = ? GROUP BY region',
                (message_id, guild_id)
            ) as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}
    
    async def get_user_geographic_selections(self, user_id: int, guild_id: int) -> List[Dict[str, Any]]:
        """Get all geographic selections for a user in a guild"""
        async with aiosqlite.connect(self.db_file) as db:
            async with db.execute('''
                SELECT gs.region, gs.message_id, gp.title, gs.selected_at
                FROM geographic_selections gs
                JOIN geographic_polls gp ON gs.message_id = gp.message_id AND gs.guild_id = gp.guild_id
                WHERE gs.user_id = ? AND gs.guild_id = ?
                ORDER BY gs.selected_at DESC
            ''', (user_id, guild_id)) as cursor:
                rows = await cursor.fetchall()
                return [
                    {
                        'region': row[0],
                        'message_id': row[1],
                        'poll_title': row[2],
                        'selected_at': row[3]
                    }
                    for row in rows
                ]
    
    # Utility Methods
    @staticmethod
    def calculate_level_from_xp(xp: int) -> int:
        """Calculate level from XP using the formula: 5 * (lvl ^ 2) + 50 * lvl + 100"""
        level = 1
        while True:
            xp_required = 5 * (level ** 2) + 50 * level + 100
            if xp < xp_required:
                return level
            level += 1
    
    @staticmethod
    def calculate_xp_for_level(level: int) -> int:
        """Calculate XP required for a specific level"""
        if level == 1:
            return 0
        return 5 * ((level - 1) ** 2) + 50 * (level - 1) + 100 