"""
Complete Anubis Database Setup - Merges existing with new requirements
"""
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def upgrade_to_anubis():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    
    # Add missing columns to existing tables
    await conn.execute("""
        -- Enhance existing token_launches table
        ALTER TABLE token_launches 
        ADD COLUMN IF NOT EXISTS time_to_bond_minutes INTEGER,
        ADD COLUMN IF NOT EXISTS bonding_completed BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS graduated_to_raydium BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS uses_jito_bundle BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS metadata_quality_score FLOAT DEFAULT 0;
        
        -- Enhance developer_wallets with Anubis fields
        ALTER TABLE developer_wallets
        ADD COLUMN IF NOT EXISTS anubis_score FLOAT DEFAULT 50,
        ADD COLUMN IF NOT EXISTS risk_rating VARCHAR(16),
        ADD COLUMN IF NOT EXISTS developer_tier VARCHAR(16),
        ADD COLUMN IF NOT EXISTS seed_consistency_score FLOAT,
        ADD COLUMN IF NOT EXISTS graduation_rate FLOAT DEFAULT 0,
        ADD COLUMN IF NOT EXISTS uses_jito BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS total_profit_sol NUMERIC(20, 9),
        ADD COLUMN IF NOT EXISTS total_profit_usd NUMERIC(20, 2);
    """)
    
    # Create new Anubis-specific tables
    await conn.execute("""
        -- Success tracking with token names
        CREATE TABLE IF NOT EXISTS developer_successes (
            id SERIAL PRIMARY KEY,
            wallet_address VARCHAR(64),
            token_address VARCHAR(64),
            token_name VARCHAR(64),
            token_symbol VARCHAR(16),
            launch_date TIMESTAMP,
            seed_amount_sol NUMERIC(18, 9),
            profit_taken_sol NUMERIC(18, 9),
            profit_taken_usd NUMERIC(20, 2),
            roi_percent FLOAT,
            platform VARCHAR(32),
            UNIQUE(wallet_address, token_address)
        );
        
        -- Platform migrations tracking
        CREATE TABLE IF NOT EXISTS platform_migrations (
            id SERIAL PRIMARY KEY,
            token_address VARCHAR(64),
            from_platform VARCHAR(32),
            to_platform VARCHAR(32),
            migration_time TIMESTAMP,
            migration_mcap NUMERIC(20, 2),
            migration_type VARCHAR(32),
            UNIQUE(token_address, from_platform, to_platform)
        );
        
        -- The rest of Anubis tables from ANUBIS_SCHEMA
    """)
    
    await conn.close()
    print("✅ Database upgraded for Anubis Scoring System")

if __name__ == "__main__":
    import asyncio
    asyncio.run(upgrade_to_anubis())