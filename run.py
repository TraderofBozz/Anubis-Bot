#!/usr/bin/env python3
"""
Anubis Bot - Main Entry Point (Fixed with Historical Scanning)
"""

import sys
import logging
import asyncio
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

class AnubisBot:
    """Main bot class with integrated historical scanning"""
    
    def __init__(self):
        """Initialize the bot"""
        self.scheduler = AsyncIOScheduler()
        self.db = None
        self.historical_scan_running = False
        self.loop = None
        
    def run(self):
        """Main synchronous entry point that creates and manages the event loop"""
        try:
            # Create new event loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Run the async initialization and main loop
            self.loop.run_until_complete(self._async_run())
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal...")
        except Exception as e:
            logger.error(f"Bot error: {e}")
            raise
        finally:
            # Cleanup
            if self.loop:
                self.loop.run_until_complete(self._cleanup())
                self.loop.close()
    
    async def _async_run(self):
        """Main async runtime"""
        try:
            # Initialize components
            await self._initialize()
            
            # Start scheduler
            await self._start_scheduler()
            
            # Start the main bot logic
            await self._run_bot()
            
        except Exception as e:
            logger.error(f"Async run error: {e}")
            raise
    
    async def _initialize(self):
        """Initialize all bot components"""
        logger.info("Initializing Anubis Bot components...")
        
        # Initialize database
        await self._initialize_database()
        
        # Import and initialize your existing bot modules here
        # from modules.telegram_bot import TelegramBot
        # self.telegram_bot = TelegramBot()
        
        logger.info("Initialization complete")
    
    async def _initialize_database(self):
        """Initialize database connection pool"""
        try:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                logger.error("DATABASE_URL not set in environment variables!")
                raise ValueError("DATABASE_URL is required")
            
            self.db = await asyncpg.create_pool(
                database_url,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            
            # Ensure required tables exist
            await self._ensure_tables_exist()
            
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _ensure_tables_exist(self):
        """Create necessary tables if they don't exist"""
        async with self.db.acquire() as conn:
            # Create system_config table for tracking scans
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    config_key VARCHAR(255) PRIMARY KEY,
                    config_value JSONB,
                    last_scan_date TIMESTAMP WITH TIME ZONE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            # Create token_launches table if not exists
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_launches (
                    id BIGSERIAL PRIMARY KEY,
                    mint_address VARCHAR(64) UNIQUE,
                    creator_wallet VARCHAR(64),
                    platform VARCHAR(32),
                    launch_time TIMESTAMP WITH TIME ZONE,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            
            logger.info("Database tables verified/created")
    
    async def _start_scheduler(self):
        """Start the APScheduler for periodic tasks"""
        # Schedule historical scan check
        # Runs immediately on start, then every 24 hours
        self.scheduler.add_job(
            self._check_and_run_historical_scan,
            'interval',
            hours=24,
            id='historical_scan_check',
            next_run_time=datetime.now(),  # Run immediately
            misfire_grace_time=3600  # 1 hour grace period
        )
        
        # Add other scheduled tasks here
        # self.scheduler.add_job(...)
        
        # Start the scheduler
        self.scheduler.start()
        logger.info("Scheduler started successfully")
    
    async def _check_and_run_historical_scan(self):
        """Check if historical scan needs to run and execute if needed"""
        if self.historical_scan_running:
            logger.warning("Historical scan already running, skipping...")
            return
        
        try:
            async with self.db.acquire() as conn:
                # Check if scan has been completed before
                result = await conn.fetchrow("""
                    SELECT config_value, last_scan_date 
                    FROM system_config 
                    WHERE config_key = 'historical_scan_complete'
                """)
                
                if not result:
                    logger.info("=" * 60)
                    logger.info("NO HISTORICAL SCAN FOUND - STARTING INITIAL SCAN")
                    logger.info("=" * 60)
                    await self._run_historical_scan()
                else:
                    last_scan = result['last_scan_date']
                    logger.info(f"Historical scan last completed: {last_scan}")
                    
                    # Optional: Re-scan if data is older than 7 days
                    if last_scan and last_scan < datetime.now(last_scan.tzinfo) - timedelta(days=7):
                        logger.info("Historical data is stale (>7 days), running update scan...")
                        await self._run_incremental_scan(last_scan)
                    else:
                        logger.info("Historical data is up to date, skipping scan")
                        
        except Exception as e:
            logger.error(f"Error checking historical scan status: {e}")
    
    async def _run_historical_scan(self):
        """Execute the full 3-year historical scan"""
        self.historical_scan_running = True
        
        try:
            logger.info("Starting full historical scan (3 years)...")
            
            # Import scanner module
            try:
                from modules.wallet_scanner import HistoricalScanner
            except ImportError:
                logger.error("wallet_scanner module not found! Creating placeholder...")
                # Create a minimal scanner for testing
                class HistoricalScanner:
                    def __init__(self, db):
                        self.db = db
                    
                    async def run_historical_scan(self, start_date, end_date):
                        logger.info(f"Placeholder scan from {start_date} to {end_date}")
                        return {"test": []}
            
            # Initialize scanner
            scanner = HistoricalScanner(self.db)
            
            # Set scan parameters (3 years)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365 * 3)
            
            logger.info(f"Scanning period: {start_date.date()} to {end_date.date()}")
            
            # Run the scan
            results = await scanner.run_historical_scan(start_date, end_date)
            
            # Process results
            total_tokens = sum(len(tokens) for tokens in results.values())
            logger.info(f"Scan found {total_tokens} total tokens")
            
            # Mark scan as complete
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO system_config (config_key, config_value, last_scan_date)
                    VALUES ('historical_scan_complete', $1, NOW())
                    ON CONFLICT (config_key) 
                    DO UPDATE SET 
                        config_value = $1,
                        last_scan_date = NOW(),
                        updated_at = NOW()
                """, {
                    'total_tokens': total_tokens,
                    'scan_date': end_date.isoformat(),
                    'platforms_scanned': list(results.keys())
                })
            
            logger.info("=" * 60)
            logger.info(f"HISTORICAL SCAN COMPLETE! Processed {total_tokens} tokens")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Historical scan failed: {e}")
        finally:
            self.historical_scan_running = False
    
    async def _run_incremental_scan(self, last_scan_date):
        """Run incremental scan from last scan date to now"""
        self.historical_scan_running = True
        
        try:
            logger.info(f"Running incremental scan from {last_scan_date}")
            
            try:
                from modules.wallet_scanner import HistoricalScanner
                scanner = HistoricalScanner(self.db)
                
                results = await scanner.run_historical_scan(
                    last_scan_date,
                    datetime.now()
                )
                
                # Update scan date
                async with self.db.acquire() as conn:
                    await conn.execute("""
                        UPDATE system_config 
                        SET last_scan_date = NOW(), 
                            updated_at = NOW()
                        WHERE config_key = 'historical_scan_complete'
                    """)
                
                logger.info("Incremental scan complete!")
                
            except ImportError:
                logger.error("Scanner module not available for incremental scan")
                
        except Exception as e:
            logger.error(f"Incremental scan error: {e}")
        finally:
            self.historical_scan_running = False
    
    async def _run_bot(self):
        """Main bot runtime loop"""
        logger.info("Anubis Bot is now running...")
        
        # Your main bot logic here
        # For now, just keep the bot alive
        try:
            while True:
                # Main bot operations
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # You can add periodic status checks here
                if not self.db:
                    logger.error("Database connection lost!")
                    break
                    
        except asyncio.CancelledError:
            logger.info("Bot runtime cancelled")
            raise
    
    async def _cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up resources...")
        
        # Stop scheduler
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            
        # Close database connection
        if self.db:
            await self.db.close()
            
        logger.info("Cleanup complete")

def main():
    """Main function - synchronous entry point"""
    logger.info("Starting Anubis Bot System...")
    
    try:
        bot = AnubisBot()
        # Don't use asyncio.run() here - let the bot handle its own event loop
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()