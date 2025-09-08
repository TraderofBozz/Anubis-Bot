"""
Anubis Bot Database Module
Handles all database operations with NO hardcoded data
"""

import asyncio
import asyncpg
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger
from contextlib import asynccontextmanager

class Database:
    """Database connection manager for Anubis Bot"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Create connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=5,
                max_size=20,
                timeout=60,
                command_timeout=60
            )
            logger.info("Database connection pool created")
            
            # Initialize schema if needed
            await self.init_schema()
            
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool"""
        async with self.pool.acquire() as connection:
            yield connection
    
    async def init_schema(self):
        """Initialize database schema"""
        async with self.acquire() as conn:
            # Check if tables exist
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'developer_wallets'
                )
            """)
            
            if not exists:
                logger.info("Creating database schema...")
                await self.create_schema(conn)
    
    async def create_schema(self, conn):
        """Create all database tables"""
        await conn.execute("""
            -- Developer wallets table with NO hardcoded data
            CREATE TABLE IF NOT EXISTS developer_wallets (
                wallet_address VARCHAR(44) PRIMARY KEY,
                wallet_alias VARCHAR(100),
                
                -- All metrics start at 0
                total_launches INTEGER DEFAULT 0,
                successful_launches INTEGER DEFAULT 0,
                success_rate NUMERIC(5,2) DEFAULT 0,
                
                -- Financial metrics
                total_earnings NUMERIC(20,2) DEFAULT 0,
                average_earnings NUMERIC(20,2) DEFAULT 0,
                highest_ath NUMERIC(20,2) DEFAULT 0,
                
                -- Timing patterns (discovered, not assumed)
                avg_time_to_bond_minutes NUMERIC(10,2),
                avg_duration_days NUMERIC(10,2),
                launch_hour_preference INTEGER[],
                launch_day_preference VARCHAR(10)[],
                
                -- Network metrics
                network_complexity_score INTEGER DEFAULT 0,
                network_size INTEGER DEFAULT 0,
                wallet_funding_source VARCHAR(50),
                uses_fresh_wallets BOOLEAN,
                
                -- Market patterns
                typical_exit_mc NUMERIC(20,2),
                uses_gradual_exit BOOLEAN,
                uses_bundle_bots BOOLEAN,
                initial_buyer_count INTEGER,
                
                -- Risk metrics
                rug_rate NUMERIC(5,2) DEFAULT 0,
                
                -- Tracking metadata
                first_seen TIMESTAMPTZ DEFAULT NOW(),
                last_active TIMESTAMPTZ,
                last_launch_time TIMESTAMPTZ,
                tracking_status VARCHAR(20) DEFAULT 'active',
                
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            -- Token launches with actual launch time
            CREATE TABLE IF NOT EXISTS token_launches (
                launch_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                mint_address VARCHAR(44) UNIQUE NOT NULL,
                creator_wallet VARCHAR(44) NOT NULL,
                
                -- Critical launch time field
                launch_time TIMESTAMPTZ NOT NULL,
                launch_signature VARCHAR(88),
                
                -- Token details
                token_name VARCHAR(100),
                token_symbol VARCHAR(20),
                initial_supply NUMERIC(40,0),
                initial_liquidity_sol NUMERIC(20,9),
                
                -- Performance metrics (filled in as observed)
                time_to_bond_minutes NUMERIC(10,2),
                peak_market_cap NUMERIC(20,2),
                time_to_peak_minutes NUMERIC(10,2),
                final_outcome VARCHAR(50), -- 'success', 'rug', 'pending'
                
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            -- Wallet activity tracking
            CREATE TABLE IF NOT EXISTS wallet_activity (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                wallet_address VARCHAR(44) NOT NULL,
                activity_time TIMESTAMPTZ NOT NULL,
                activity_type VARCHAR(50), -- 'deposit', 'withdrawal', 'launch'
                amount_sol NUMERIC(20,9),
                transaction_signature VARCHAR(88),
                metadata JSONB DEFAULT '{}',
                
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            -- User tracking preferences
            CREATE TABLE IF NOT EXISTS tracked_wallets (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                user_id BIGINT NOT NULL,
                wallet_address VARCHAR(44) NOT NULL,
                alias VARCHAR(100),
                is_active BOOLEAN DEFAULT TRUE,
                alert_threshold_sol NUMERIC(20,9) DEFAULT 10,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                
                UNIQUE(user_id, wallet_address)
            );
            
            -- Telegram users
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            
            -- Indexes for performance
            CREATE INDEX IF NOT EXISTS idx_launches_time ON token_launches(launch_time DESC);
            CREATE INDEX IF NOT EXISTS idx_launches_creator ON token_launches(creator_wallet);
            CREATE INDEX IF NOT EXISTS idx_activity_wallet ON wallet_activity(wallet_address, activity_time DESC);
            CREATE INDEX IF NOT EXISTS idx_tracked_user ON tracked_wallets(user_id, is_active);
        """)
        
        logger.info("Database schema created successfully")
    
    # Data access methods - NO hardcoded data
    
    async def get_developer(self, wallet_address: str) -> Optional[Dict]:
        """Get developer profile - returns None if not found"""
        async with self.acquire() as conn:
            return await conn.fetchrow("""
                SELECT * FROM developer_wallets 
                WHERE wallet_address = $1
            """, wallet_address)
    
    async def upsert_developer(self, wallet_address: str, **kwargs) -> None:
        """Insert or update developer - only with observed data"""
        async with self.acquire() as conn:
            # Build update fields dynamically
            update_fields = []
            values = [wallet_address]
            param_count = 1
            
            for key, value in kwargs.items():
                param_count += 1
                update_fields.append(f"{key} = ${param_count}")
                values.append(value)
            
            if update_fields:
                query = f"""
                    INSERT INTO developer_wallets (wallet_address, {', '.join(kwargs.keys())})
                    VALUES ($1, {', '.join(f'${i+2}' for i in range(len(kwargs)))})
                    ON CONFLICT (wallet_address) DO UPDATE SET
                    {', '.join(update_fields)},
                    updated_at = NOW()
                """
                await conn.execute(query, *values)
    
    async def record_launch(self, launch_data: Dict) -> None:
        """Record a new token launch"""
        async with self.acquire() as conn:
            await conn.execute("""
                INSERT INTO token_launches (
                    mint_address, creator_wallet, launch_time,
                    launch_signature, token_name, token_symbol,
                    initial_supply, initial_liquidity_sol
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (mint_address) DO NOTHING
            """, 
                launch_data['mint_address'],
                launch_data['creator_wallet'],
                launch_data['launch_time'],
                launch_data.get('launch_signature'),
                launch_data.get('token_name'),
                launch_data.get('token_symbol'),
                launch_data.get('initial_supply'),
                launch_data.get('initial_liquidity_sol')
            )
    
    async def record_activity(self, wallet: str, activity_type: str, 
                            amount: float = None, signature: str = None) -> None:
        """Record wallet activity"""
        async with self.acquire() as conn:
            await conn.execute("""
                INSERT INTO wallet_activity (
                    wallet_address, activity_time, activity_type,
                    amount_sol, transaction_signature
                ) VALUES ($1, $2, $3, $4, $5)
            """, wallet, datetime.utcnow(), activity_type, amount, signature)
    
    async def get_recent_launches(self, hours: int = 24) -> List[Dict]:
        """Get recent launches - returns actual data only"""
        async with self.acquire() as conn:
            rows = await conn.fetch("""
                SELECT tl.*, dw.wallet_alias, dw.success_rate
                FROM token_launches tl
                LEFT JOIN developer_wallets dw ON tl.creator_wallet = dw.wallet_address
                WHERE tl.launch_time > $1
                ORDER BY tl.launch_time DESC
            """, datetime.utcnow() - timedelta(hours=hours))
            
            return [dict(row) for row in rows]
    
    async def get_tracked_wallets(self, user_id: int) -> List[Dict]:
        """Get wallets tracked by a user"""
        async with self.acquire() as conn:
            rows = await conn.fetch("""
                SELECT tw.*, dw.total_launches, dw.success_rate
                FROM tracked_wallets tw
                LEFT JOIN developer_wallets dw ON tw.wallet_address = dw.wallet_address
                WHERE tw.user_id = $1 AND tw.is_active = TRUE
                ORDER BY tw.created_at DESC
            """, user_id)
            
            return [dict(row) for row in rows]
    
    async def track_wallet(self, user_id: int, wallet_address: str, 
                          alias: str = None, threshold: float = 10.0) -> bool:
        """Add wallet to user's tracking list"""
        async with self.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO tracked_wallets (
                        user_id, wallet_address, alias, alert_threshold_sol
                    ) VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, wallet_address) 
                    DO UPDATE SET is_active = TRUE, alias = EXCLUDED.alias
                """, user_id, wallet_address, alias, threshold)
                return True
            except Exception as e:
                logger.error(f"Error tracking wallet: {e}")
                return False
    
    async def untrack_wallet(self, user_id: int, wallet_address: str) -> bool:
        """Remove wallet from tracking"""
        async with self.acquire() as conn:
            result = await conn.execute("""
                UPDATE tracked_wallets 
                SET is_active = FALSE 
                WHERE user_id = $1 AND wallet_address = $2
            """, user_id, wallet_address)
            
            return result.split()[-1] != '0'
    
    async def get_top_developers(self, limit: int = 10) -> List[Dict]:
        """Get top developers by success rate - only those with actual data"""
        async with self.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM developer_wallets
                WHERE total_launches > 0
                ORDER BY success_rate DESC, total_launches DESC
                LIMIT $1
            """, limit)
            
            return [dict(row) for row in rows] if rows else []
    
    async def upsert_user(self, user_id: int, username: str = None, 
                         first_name: str = None) -> None:
        """Create or update user"""
        async with self.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    is_active = TRUE
            """, user_id, username, first_name)