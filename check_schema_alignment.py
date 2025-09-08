#!/usr/bin/env python3
"""
Complete Schema Alignment Checker for Anubis Bot
Checks all table and column references in scanner against actual database schema
"""

import re
import psycopg2
import os
from dotenv import load_dotenv
from collections import defaultdict

# Load environment
load_dotenv()

# Define CORRECT database schema (what we created)
CORRECT_SCHEMA = {
    'anubis.wallet_profiles': [
        'wallet_address', 'anubis_score', 'developer_tier', 'risk_level',
        'total_launches', 'successful_launches', 'failed_launches', 'rugged_launches',
        'success_rate', 'rug_rate', 'estimated_earnings_sol', 'largest_success_mcap',
        'average_hold_time_hours', 'quick_dump_rate', 'average_launches_per_day',
        'peak_launch_hour', 'peak_launch_day', 'preferred_launch_times',
        'launch_velocity_score', 'connected_wallets_count', 'network_complexity_score',
        'uses_jito', 'uses_mev', 'first_seen_at', 'last_seen_at', 'last_launch_at',
        'profile_updated_at', 'days_active', 'primary_platform', 'platforms_used',
        'is_active', 'is_flagged', 'flag_reason', 'tracking_priority', 'notes', 'tags'
    ],
    'anubis.token_launches': [
        'id', 'mint_address', 'token_name', 'token_symbol', 'token_uri',
        'creator_wallet', 'deployer_wallet', 'fee_payer_wallet',
        'launch_timestamp', 'launch_block_slot', 'launch_signature', 'platform',
        'initial_supply', 'decimals', 'initial_liquidity_sol', 'initial_price',
        'metadata_fetched', 'metadata_fetch_attempts', 'metadata_fetch_error',
        'metadata_fetched_at', 'is_graduated', 'graduated_at', 'is_rugged',
        'rugged_at', 'current_mcap', 'current_price', 'peak_mcap', 'peak_mcap_at',
        'time_to_peak_minutes', 'time_to_100k_minutes', 'time_to_1m_minutes',
        'has_twitter', 'twitter_handle', 'has_telegram', 'telegram_link',
        'has_website', 'website_url', 'alert_sent', 'alert_sent_at',
        'alert_channel', 'alert_tier', 'created_at', 'updated_at'
    ],
    'anubis.wallet_relationships': [
        'id', 'wallet_a', 'wallet_b', 'relationship_type', 'confidence_score',
        'transaction_count', 'total_volume_sol', 'evidence',
        'first_interaction_at', 'last_interaction_at', 'discovered_at', 'updated_at'
    ],
    'anubis.token_performance_history': [
        'id', 'mint_address', 'timestamp', 'price', 'market_cap', 'volume_24h',
        'liquidity', 'holder_count', 'buy_count_1h', 'sell_count_1h',
        'unique_buyers_1h', 'unique_sellers_1h', 'price_change_1h',
        'volume_change_1h', 'buy_sell_ratio'
    ],
    'anubis.developer_patterns': [
        'wallet_address', 'launch_hours', 'launch_days', 'launch_intervals',
        'avg_time_between_launches_minutes', 'std_dev_launch_interval',
        'launches_per_session', 'session_duration_minutes',
        'typical_initial_buy_sol', 'typical_sell_timing_minutes',
        'holds_to_graduation_rate', 'panic_sell_rate', 'creates_social_rate',
        'reuses_social_accounts', 'marketing_spend_estimate_sol',
        'uses_same_rpc', 'common_rpc_endpoint', 'uses_vpn',
        'consistent_gas_settings', 'analyzed_at', 'pattern_confidence'
    ],
    'anubis.successful_tokens_archive': [
        'mint_address', 'token_name', 'token_symbol', 'creator_wallet',
        'peak_market_cap', 'peak_reached_at', 'time_to_peak_hours',
        'launched_at', 'initial_liquidity_sol', 'graduated_at',
        'roi_from_launch', 'sustained_above_100k_hours',
        'developer_profit_sol', 'developer_sell_pattern', 'notes', 'archived_at'
    ],
    'anubis.alert_history': [
        'id', 'mint_address', 'creator_wallet', 'alert_type', 'alert_tier',
        'channel_sent_to', 'anubis_score_at_time', 'developer_tier_at_time',
        'risk_level_at_time', 'message_text', 'sent_at', 'delivery_status',
        'error_message', 'views', 'clicks'
    ],
    'anubis.metadata_retry_queue': [
        'id', 'mint_address', 'retry_count', 'max_retries', 'last_attempt_at',
        'next_attempt_at', 'error_message', 'priority', 'created_at'
    ],
    'anubis.platform_data': [
        'id', 'mint_address', 'platform', 'platform_token_id', 'platform_pool_id',
        'platform_rank', 'platform_score', 'bonding_curve_progress',
        'platform_data', 'fetched_at'
    ]
}

def check_scanner_file(filename='anubis_historical_scanner.py'):
    """Parse scanner file and find all SQL references"""
    
    print("🔍 COMPLETE SCHEMA ALIGNMENT CHECK")
    print("=" * 60)
    
    issues_found = []
    
    try:
        with open(filename, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"❌ Could not find {filename}")
        return
    
    # Find all SQL operations
    sql_patterns = {
        'INSERT': r'INSERT\s+INTO\s+(\w+(?:\.\w+)?)',
        'UPDATE': r'UPDATE\s+(\w+(?:\.\w+)?)',
        'SELECT': r'FROM\s+(\w+(?:\.\w+)?)',
        'DELETE': r'DELETE\s+FROM\s+(\w+(?:\.\w+)?)',
        'CREATE': r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+(?:\.\w+)?)',
    }
    
    found_references = defaultdict(list)
    
    for operation, pattern in sql_patterns.items():
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            table_ref = match.group(1).lower()
            # Get context (line number and surrounding text)
            line_num = content[:match.start()].count('\n') + 1
            context_start = max(0, match.start() - 100)
            context_end = min(len(content), match.end() + 100)
            context = content[context_start:context_end].replace('\n', ' ').strip()
            
            found_references[table_ref].append({
                'operation': operation,
                'line': line_num,
                'context': context
            })
    
    print("\n📋 FOUND TABLE REFERENCES IN SCANNER:\n")
    for table, refs in sorted(found_references.items()):
        print(f"  • {table} ({len(refs)} references)")
        for ref in refs[:2]:  # Show first 2 references
            print(f"    Line {ref['line']}: {ref['operation']}")
    
    # Check for mismatches
    print("\n⚠️  ISSUES FOUND:\n")
    
    # Common mistakes to check
    wrong_mappings = {
        'token_launches': 'anubis.token_launches',
        'wallet_profiles': 'anubis.wallet_profiles',
        'anubis_wallet_profiles': 'anubis.wallet_profiles',
        'wallet_relationships': 'anubis.wallet_relationships',
        'token_performance_history': 'anubis.token_performance_history',
        'developer_patterns': 'anubis.developer_patterns',
        'successful_tokens_archive': 'anubis.successful_tokens_archive',
        'alert_history': 'anubis.alert_history',
        'metadata_retry_queue': 'anubis.metadata_retry_queue',
        'platform_data': 'anubis.platform_data'
    }
    
    for wrong_table, correct_table in wrong_mappings.items():
        if wrong_table in found_references:
            issues_found.append((wrong_table, correct_table))
            print(f"❌ Found '{wrong_table}' → Should be '{correct_table}'")
            for ref in found_references[wrong_table]:
                print(f"   Line {ref['line']}: {ref['operation']}")
    
    # Check column name mismatches in INSERT statements
    print("\n📊 CHECKING COLUMN NAMES:\n")
    
    # Extract INSERT column lists
    insert_pattern = r'INSERT\s+INTO\s+(\w+(?:\.\w+)?)\s*\(([^)]+)\)'
    insert_matches = re.finditer(insert_pattern, content, re.IGNORECASE | re.DOTALL)
    
    for match in insert_matches:
        table_ref = match.group(1).lower()
        columns_str = match.group(2)
        columns = [col.strip() for col in columns_str.split(',')]
        
        # Map wrong table name to correct one
        correct_table = wrong_mappings.get(table_ref, table_ref)
        if not correct_table.startswith('anubis.'):
            correct_table = 'anubis.' + correct_table
        
        if correct_table in CORRECT_SCHEMA:
            valid_columns = CORRECT_SCHEMA[correct_table]
            for col in columns:
                col_clean = col.strip().lower()
                if col_clean not in valid_columns:
                    print(f"❌ Column '{col_clean}' not in {correct_table}")
                    print(f"   Valid columns: {', '.join(valid_columns[:5])}...")
    
    # Generate fix commands
    if issues_found:
        print("\n🔧 FIX COMMANDS:\n")
        print("# Backup first")
        print(f"cp {filename} {filename}.backup")
        print()
        for wrong, correct in issues_found:
            # Exact word boundary replacement to avoid partial matches
            print(f"# Replace '{wrong}' with '{correct}'")
            print(f"sed -i 's/\\b{wrong}\\b/{correct}/g' {filename}")
    
    return issues_found

def verify_database_schema():
    """Connect to database and verify actual schema"""
    print("\n🔍 VERIFYING ACTUAL DATABASE SCHEMA")
    print("=" * 60)
    
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Get all tables in anubis schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'anubis'
            ORDER BY table_name
        """)
        
        actual_tables = [row[0] for row in cur.fetchall()]
        print("\n✅ Tables in database:")
        for table in actual_tables:
            print(f"  • anubis.{table}")
        
        # Check each table's columns
        print("\n📋 Verifying columns for key tables:")
        
        for table in ['wallet_profiles', 'token_launches']:
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'anubis' AND table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            
            columns = cur.fetchall()
            print(f"\n  anubis.{table}:")
            for col_name, col_type in columns[:10]:  # Show first 10
                print(f"    • {col_name} ({col_type})")
            if len(columns) > 10:
                print(f"    ... and {len(columns)-10} more columns")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

if __name__ == "__main__":
    # Check scanner file
    issues = check_scanner_file()
    
    # Verify database
    verify_database_schema()
    
    # Summary
    print("\n" + "=" * 60)
    if issues:
        print(f"⚠️  Found {len(issues)} table reference issues to fix")
        print("Run the sed commands above to fix them automatically")
    else:
        print("✅ No issues found - scanner appears aligned with database!")