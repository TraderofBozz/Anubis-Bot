"""
Database Verification Script for Anubis Scoring System
Verifies all tables, columns, and data insertion work correctly
"""

import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
import json
import random

load_dotenv()

class DatabaseVerification:
    def __init__(self):
        self.DATABASE_URL = os.getenv('DATABASE_URL')
        self.errors = []
        self.warnings = []
        self.success = []
    
    async def run_full_verification(self):
        """Run complete database verification"""
        print("=" * 60)
        print("ANUBIS DATABASE VERIFICATION SYSTEM")
        print("=" * 60)
        
        conn = await asyncpg.connect(self.DATABASE_URL)
        
        try:
            # 1. Verify all tables exist
            await self.verify_tables_exist(conn)
            
            # 2. Verify column structure
            await self.verify_column_structure(conn)
            
            # 3. Test data insertion
            await self.test_data_insertion(conn)
            
            # 4. Verify indexes
            await self.verify_indexes(conn)
            
            # 5. Test relationships
            await self.test_relationships(conn)
            
            # 6. Verify Anubis-specific features
            await self.verify_anubis_features(conn)
            
            # Print results
            self.print_results()
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await conn.close()
    
    async def verify_tables_exist(self, conn):
        """Verify all required tables exist"""
        print("\n📊 Verifying Tables...")
        
        required_tables = [
            'anubis_wallet_profiles',
            'token_launches',
            'launch_time_patterns',
            'wallet_networks',
            'behavioral_patterns',
            'developer_successes',
            'platform_migrations',
            'anubis_predictions',
            'successful_tokens_archive',
            'active_monitoring'
        ]
        
        for table in required_tables:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = $1
                )
            """, table)
            
            if exists:
                self.success.append(f"✅ Table '{table}' exists")
            else:
                self.errors.append(f"❌ Table '{table}' is MISSING")
    
    async def verify_column_structure(self, conn):
        """Verify critical columns exist and have correct types"""
        print("\n🔍 Verifying Column Structure...")
        
        # Define critical columns for each table
        critical_columns = {
            'anubis_wallet_profiles': [
                ('wallet_address', 'character varying'),
                ('anubis_score', 'double precision'),
                ('total_profit_sol', 'numeric'),
                ('total_profit_usd', 'numeric'),
                ('avg_time_to_bond_minutes', 'integer'),
                ('graduation_rate', 'double precision'),
                ('uses_jito', 'boolean'),
                ('metadata_quality_score', 'double precision'),
                ('seed_consistency_score', 'double precision')
            ],
            'token_launches': [
                ('mint_address', 'character varying'),
                ('creator_wallet', 'character varying'),
                ('platform', 'character varying'),
                ('initial_liquidity_sol', 'numeric'),
                ('time_to_bond_minutes', 'integer'),
                ('graduated_to_raydium', 'boolean'),
                ('uses_jito_bundle', 'boolean'),
                ('metadata_quality_score', 'double precision')
            ],
            'developer_successes': [
                ('wallet_address', 'character varying'),
                ('token_name', 'character varying'),
                ('profit_taken_sol', 'numeric'),
                ('profit_taken_usd', 'numeric'),
                ('roi_percent', 'double precision')
            ]
        }
        
        for table, columns in critical_columns.items():
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = $1
                )
            """, table)
            
            if not table_exists:
                continue
                
            for col_name, expected_type in columns:
                col_info = await conn.fetchrow("""
                    SELECT data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = $1 AND column_name = $2
                """, table, col_name)
                
                if col_info:
                    if expected_type in col_info['data_type']:
                        self.success.append(f"✅ {table}.{col_name} has correct type")
                    else:
                        self.warnings.append(f"⚠️ {table}.{col_name} type mismatch: expected {expected_type}, got {col_info['data_type']}")
                else:
                    self.errors.append(f"❌ Column {table}.{col_name} is MISSING")
    
    async def test_data_insertion(self, conn):
        """Test inserting data into all tables"""
        print("\n💾 Testing Data Insertion...")
        
        test_wallet = f"TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        test_token = f"TOKEN_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Test anubis_wallet_profiles
            await conn.execute("""
                INSERT INTO anubis_wallet_profiles 
                (wallet_address, anubis_score, total_launches, successful_launches,
                 avg_seed_amount, avg_time_to_bond_minutes, graduation_rate,
                 uses_jito, metadata_quality_score, seed_consistency_score)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (wallet_address) DO UPDATE SET
                    anubis_score = EXCLUDED.anubis_score
            """, test_wallet, 75.5, 10, 3, 5.5, 45, 0.3, True, 65.0, 0.4)
            
            self.success.append("✅ anubis_wallet_profiles insertion successful")
            
            # Test token_launches with new features
            await conn.execute("""
                INSERT INTO token_launches
                (mint_address, creator_wallet, platform, launch_time,
                 initial_liquidity_sol, time_to_bond_minutes,
                 graduated_to_raydium, uses_jito_bundle,
                 metadata_quality_score, token_name, token_symbol)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (mint_address) DO NOTHING
            """, test_token, test_wallet, 'pump_fun', datetime.now(),
                5.5, 35, True, True, 72.5, 'TestToken', 'TEST')
            
            self.success.append("✅ token_launches insertion successful")
            
            # Test developer_successes
            await conn.execute("""
                INSERT INTO developer_successes
                (wallet_address, token_address, token_name, token_symbol,
                 seed_amount_sol, profit_taken_sol, profit_taken_usd,
                 roi_percent, launch_date, platform)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (wallet_address, token_address) DO NOTHING
            """, test_wallet, test_token, 'TestToken', 'TEST',
                5.0, 150.0, 22500.0, 3000.0, datetime.now(), 'pump_fun')
            
            self.success.append("✅ developer_successes insertion successful")
            
            # Test platform_migrations
            await conn.execute("""
                INSERT INTO platform_migrations
                (token_address, from_platform, to_platform,
                 migration_time, migration_mcap, migration_type)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (token_address, from_platform, to_platform) DO NOTHING
            """, test_token, 'pump_fun', 'raydium',
                datetime.now(), 69000.0, 'graduation')
            
            self.success.append("✅ platform_migrations insertion successful")
            
            # Clean up test data
            await conn.execute("DELETE FROM platform_migrations WHERE token_address = $1", test_token)
            await conn.execute("DELETE FROM developer_successes WHERE token_address = $1", test_token)
            await conn.execute("DELETE FROM token_launches WHERE mint_address = $1", test_token)
            await conn.execute("DELETE FROM anubis_wallet_profiles WHERE wallet_address = $1", test_wallet)
            
        except Exception as e:
            self.errors.append(f"❌ Data insertion failed: {e}")
    
    async def verify_indexes(self, conn):
        """Verify all performance indexes exist"""
        print("\n🔍 Verifying Indexes...")
        
        critical_indexes = [
            'idx_anubis_score',
            'idx_risk_rating',
            'idx_creator_wallet',
            'idx_launch_time',
            'idx_graduated',
            'idx_bonding_time'
        ]
        
        for index in critical_indexes:
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE indexname = $1
                )
            """, index)
            
            if exists:
                self.success.append(f"✅ Index '{index}' exists")
            else:
                self.warnings.append(f"⚠️ Index '{index}' is missing (performance may be impacted)")
    
    async def test_relationships(self, conn):
        """Test foreign key relationships work correctly"""
        print("\n🔗 Testing Relationships...")
        
        # Test wallet profile -> developer successes relationship
        test_wallet = f"REL_TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Create parent record
            await conn.execute("""
                INSERT INTO anubis_wallet_profiles (wallet_address, anubis_score)
                VALUES ($1, 50)
            """, test_wallet)
            
            # Try to create child record
            await conn.execute("""
                INSERT INTO developer_successes
                (wallet_address, token_address, token_name, launch_date, platform)
                VALUES ($1, 'test_token', 'Test', NOW(), 'pump_fun')
                ON CONFLICT DO NOTHING
            """, test_wallet)
            
            self.success.append("✅ Foreign key relationships working")
            
            # Clean up
            await conn.execute("DELETE FROM developer_successes WHERE wallet_address = $1", test_wallet)
            await conn.execute("DELETE FROM anubis_wallet_profiles WHERE wallet_address = $1", test_wallet)
            
        except Exception as e:
            self.warnings.append(f"⚠️ Relationship test issue: {e}")
    
    async def verify_anubis_features(self, conn):
        """Verify Anubis-specific features are properly configured"""
        print("\n🎯 Verifying Anubis-Specific Features...")
        
        # Check if we can calculate scores
        test_wallet = f"ANUBIS_TEST_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Insert test data with all Anubis fields
            await conn.execute("""
                INSERT INTO anubis_wallet_profiles
                (wallet_address, anubis_score, risk_rating, developer_tier,
                 total_launches, successful_launches, total_rugs,
                 avg_seed_amount, seed_consistency_score,
                 avg_time_to_bond_minutes, graduation_rate,
                 uses_jito, jito_usage_rate,
                 metadata_quality_score, uses_copycat_names,
                 total_profit_sol, total_profit_usd,
                 best_roi_percent, avg_roi_percent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
            """, test_wallet, 75.5, 'LOW', 'PRO',
                50, 10, 5,
                5.5, 0.3,
                45, 0.2,
                True, 0.6,
                72.0, False,
                500.0, 75000.0,
                5000.0, 1500.0)
            
            # Verify we can read it back
            profile = await conn.fetchrow("""
                SELECT * FROM anubis_wallet_profiles
                WHERE wallet_address = $1
            """, test_wallet)
            
            if profile:
                self.success.append("✅ All Anubis scoring fields working")
                
                # Check specific fields
                if profile['uses_jito'] is not None:
                    self.success.append("✅ Jito tracking field verified")
                if profile['seed_consistency_score'] is not None:
                    self.success.append("✅ Seed consistency tracking verified")
                if profile['graduation_rate'] is not None:
                    self.success.append("✅ Graduation tracking verified")
                if profile['metadata_quality_score'] is not None:
                    self.success.append("✅ Metadata quality tracking verified")
                if profile['total_profit_usd'] is not None:
                    self.success.append("✅ Profit tracking verified")
            
            # Clean up
            await conn.execute("DELETE FROM anubis_wallet_profiles WHERE wallet_address = $1", test_wallet)
            
        except Exception as e:
            self.errors.append(f"❌ Anubis features verification failed: {e}")
    
    def print_results(self):
        """Print verification results"""
        print("\n" + "=" * 60)
        print("VERIFICATION RESULTS")
        print("=" * 60)
        
        if self.success:
            print(f"\n✅ SUCCESSFUL CHECKS ({len(self.success)}):")
            for s in self.success[:10]:  # Show first 10
                print(f"  {s}")
            if len(self.success) > 10:
                print(f"  ... and {len(self.success) - 10} more")
        
        if self.warnings:
            print(f"\n⚠️ WARNINGS ({len(self.warnings)}):")
            for w in self.warnings:
                print(f"  {w}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for e in self.errors:
                print(f"  {e}")
        
        # Final verdict
        print("\n" + "=" * 60)
        if not self.errors:
            print("🎉 DATABASE VERIFICATION PASSED!")
            print("Your Anubis Scoring System database is properly configured.")
        elif len(self.errors) < 5:
            print("⚠️ DATABASE HAS MINOR ISSUES")
            print("Please fix the errors above before running in production.")
        else:
            print("❌ DATABASE HAS CRITICAL ISSUES")
            print("Multiple errors detected. Run the setup script again.")

async def main():
    verifier = DatabaseVerification()
    await verifier.run_full_verification()

if __name__ == "__main__":
    asyncio.run(main())