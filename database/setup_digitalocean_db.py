# database/setup_digitalocean_db.py
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class DatabaseSetup:
    def __init__(self):
        # DigitalOcean connection string format
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL not found in .env file")
    
    async def reset_database(self, confirm=False):
        """Completely reset database - WARNING: Deletes all data"""
        if not confirm:
            print("⚠️  WARNING: This will delete ALL data!")
            response = input("Type 'DELETE ALL' to confirm: ")
            if response != "DELETE ALL":
                print("Cancelled.")
                return
        
        conn = await asyncpg.connect(self.DATABASE_URL)
        
        try:
            # Drop existing tables
            await conn.execute("DROP TABLE IF EXISTS active_monitoring CASCADE")
            await conn.execute("DROP TABLE IF EXISTS successful_tokens_archive CASCADE")
            await conn.execute("DROP TABLE IF EXISTS token_launches CASCADE")
            await conn.execute("DROP TABLE IF EXISTS historical_wallet_profiles CASCADE")
            
            print("✅ Old tables dropped")
            
        finally:
            await conn.close()
    
    async def create_tables(self):
        """Create all necessary tables with proper schema"""
        conn = await asyncpg.connect(self.DATABASE_URL)
        
        try:
            # 1. Historical wallet profiles (developers)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS historical_wallet_profiles (
                    wallet_address VARCHAR(64) PRIMARY KEY,
                    total_launches INTEGER DEFAULT 0,
                    successful_launches INTEGER DEFAULT 0,
                    total_rugs INTEGER DEFAULT 0,
                    avg_seed_amount NUMERIC(18, 9),
                    avg_peak_mcap NUMERIC(20, 2),
                    success_rate NUMERIC(5, 4),
                    risk_score NUMERIC(5, 2),
                    first_seen TIMESTAMP,
                    last_active TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # 2. Token launches table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_launches (
                    id SERIAL PRIMARY KEY,
                    mint_address VARCHAR(64) UNIQUE NOT NULL,
                    creator_wallet VARCHAR(64) NOT NULL,
                    platform VARCHAR(32) NOT NULL,
                    launch_time TIMESTAMP NOT NULL,
                    initial_liquidity_sol NUMERIC(18, 9),
                    signature VARCHAR(128),
                    token_name VARCHAR(64),
                    token_symbol VARCHAR(16),
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # 3. Create indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_wallet 
                ON token_launches(creator_wallet)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_launch_time 
                ON token_launches(launch_time DESC)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_platform 
                ON token_launches(platform)
            """)
            
            # 4. Successful tokens archive
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS successful_tokens_archive (
                    mint_address VARCHAR(64) PRIMARY KEY,
                    creator_wallet VARCHAR(64) NOT NULL,
                    platform VARCHAR(32),
                    launch_date TIMESTAMP,
                    peak_mcap NUMERIC(20, 2),
                    current_mcap NUMERIC(20, 2),
                    volume_24h NUMERIC(20, 2),
                    holders INTEGER,
                    last_updated TIMESTAMP DEFAULT NOW()
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_creator_success 
                ON successful_tokens_archive(creator_wallet)
            """)
            
            # 5. Active monitoring table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS active_monitoring (
                    id SERIAL PRIMARY KEY,
                    wallet_address VARCHAR(64) NOT NULL,
                    token_address VARCHAR(64),
                    platform VARCHAR(32),
                    detected_at TIMESTAMP DEFAULT NOW(),
                    alert_sent BOOLEAN DEFAULT FALSE,
                    alert_type VARCHAR(32),
                    metadata JSONB DEFAULT '{}'
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wallet_monitoring 
                ON active_monitoring(wallet_address, detected_at DESC)
            """)
            
            # 6. Create a function for automatic 90-day cleanup
            await conn.execute("""
                CREATE OR REPLACE FUNCTION cleanup_old_launches()
                RETURNS void AS $$
                BEGIN
                    DELETE FROM token_launches 
                    WHERE launch_time < NOW() - INTERVAL '90 days';
                    
                    DELETE FROM active_monitoring 
                    WHERE detected_at < NOW() - INTERVAL '90 days';
                END;
                $$ LANGUAGE plpgsql;
            """)
            
            print("✅ All tables created successfully")
            
            # Verify tables
            tables = await conn.fetch("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            
            print("\n📊 Created tables:")
            for table in tables:
                count = await conn.fetchval(
                    f"SELECT COUNT(*) FROM {table['tablename']}"
                )
                print(f"  - {table['tablename']}: {count} rows")
                
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            raise
        finally:
            await conn.close()
    
    async def verify_schema(self):
        """Verify all tables have correct columns"""
        conn = await asyncpg.connect(self.DATABASE_URL)
        
        try:
            # Check token_launches columns
            columns = await conn.fetch("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'token_launches'
                ORDER BY ordinal_position
            """)
            
            print("\n🔍 Schema verification for token_launches:")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']} "
                      f"{'(nullable)' if col['is_nullable'] == 'YES' else '(required)'}")
            
            # Test insert
            test_wallet = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            test_mint = f"MINT_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            await conn.execute("""
                INSERT INTO token_launches 
                (mint_address, creator_wallet, platform, launch_time, initial_liquidity_sol)
                VALUES ($1, $2, $3, $4, $5)
            """, test_mint, test_wallet, "pump_fun", datetime.now(), 5.0)
            
            # Verify insert worked
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM token_launches WHERE mint_address = $1",
                test_mint
            )
            
            if result == 1:
                print("\n✅ Database insert test passed")
                # Clean up test data
                await conn.execute(
                    "DELETE FROM token_launches WHERE mint_address = $1",
                    test_mint
                )
            
        finally:
            await conn.close()
    
    async def create_maintenance_cron(self):
        """Set up maintenance schedule (if using pg_cron)"""
        conn = await asyncpg.connect(self.DATABASE_URL)
        
        try:
            # Check if pg_cron is available
            extensions = await conn.fetch("""
                SELECT extname FROM pg_extension WHERE extname = 'pg_cron'
            """)
            
            if extensions:
                # Schedule daily cleanup at 2 AM
                await conn.execute("""
                    SELECT cron.schedule(
                        'cleanup-old-data',
                        '0 2 * * *',
                        'SELECT cleanup_old_launches();'
                    )
                """)
                print("✅ Scheduled daily cleanup job")
            else:
                print("ℹ️  pg_cron not available - implement cleanup in Python cron")
                
        except Exception as e:
            print(f"ℹ️  Could not set up pg_cron: {e}")
        finally:
            await conn.close()

async def main():
    setup = DatabaseSetup()
    
    print("🚀 DigitalOcean Database Setup")
    print("-" * 40)
    print("1. Reset database (delete all data)")
    print("2. Create/update tables (keep existing data)")
    print("3. Verify schema only")
    print("4. Full setup (reset + create + verify)")
    
    choice = input("\nSelect option (1-4): ")
    
    if choice == "1":
        await setup.reset_database()
    elif choice == "2":
        await setup.create_tables()
        await setup.verify_schema()
    elif choice == "3":
        await setup.verify_schema()
    elif choice == "4":
        await setup.reset_database()
        await setup.create_tables()
        await setup.verify_schema()
        await setup.create_maintenance_cron()
        print("\n✅ Full setup complete!")
    else:
        print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())