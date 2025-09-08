# test_minimal_scan.py
import asyncio
from datetime import datetime, timedelta
from modules.wallet_scanner import WalletScanner
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def test_minimal_scan():
    """Run a very small test scan - just 1 hour of data"""
    
    # Create database pool
    db_pool = await asyncpg.create_pool(os.getenv('DATABASE_URL'))
    
    try:
        scanner = WalletScanner(db_pool)
        
        # Test with just 1 hour of recent data
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=1)  # Just 1 hour!
        
        print(f"🧪 Running TEST scan: {start_date} to {end_date}")
        print("This should use minimal RPC calls...")
        
        # Run the scan
        results = await scanner.run_historical_scan(start_date, end_date)
        
        # Show results
        total_found = sum(len(v) for v in results.values())
        print(f"\n✅ Test Results:")
        print(f"  - Total launches found: {total_found}")
        print(f"  - Pump.fun: {len(results.get('pump_fun', []))}")
        print(f"  - Raydium LaunchLab: {len(results.get('raydium_launchlab', []))}")
        
        # Check what got saved to database
        async with db_pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM token_launches")
            print(f"  - Saved to database: {count} records")
            
            # Show a sample
            sample = await conn.fetch("""
                SELECT creator_wallet, platform, launch_time 
                FROM token_launches 
                LIMIT 5
            """)
            
            if sample:
                print("\n📊 Sample data:")
                for row in sample:
                    print(f"    {row['creator_wallet'][:8]}... on {row['platform']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(test_minimal_scan())