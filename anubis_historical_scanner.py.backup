"""
Complete Historical Scanner with Full Anubis Scoring System
Scans past launches AND calculates all scoring metrics
"""

import asyncio
import asyncpg
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import httpx
from loguru import logger
from dotenv import load_dotenv
import numpy as np
from enum import Enum
from dataclasses import dataclass

# Load environment variables
load_dotenv()

# ==================== ANUBIS CONFIGURATION ====================

class TimeSlot(Enum):
    """Critical time slots for launch patterns"""
    ASIA_MORNING = (22, 2)      # 10 PM - 2 AM UTC (Asia morning)
    EU_MORNING = (6, 10)        # 6 AM - 10 AM UTC
    US_MORNING = (13, 17)       # 1 PM - 5 PM UTC (US morning)
    PEAK_DEGEN = (0, 4)         # Midnight - 4 AM UTC (peak degen hours)
    WEEKEND = "weekend"

class LaunchVelocity(Enum):
    """Launch frequency patterns"""
    SERIAL_SPAMMER = "serial_spammer"     # >5 launches/day
    HIGH_FREQUENCY = "high_frequency"      # 2-5 launches/day
    MODERATE = "moderate"                  # 3-10 launches/week
    SELECTIVE = "selective"                # <3 launches/week

@dataclass
class AnubisWeights:
    """Configurable scoring weights"""
    # Historical Performance (40%)
    success_rate: float = 0.15
    avg_mcap_achieved: float = 0.10
    rug_rate: float = 0.15
    total_earnings: float = 0.10  # Added earnings weight
    
    # Launch Patterns (30%)
    time_consistency: float = 0.10
    velocity_pattern: float = 0.10
    platform_preference: float = 0.10
    
    # Behavioral Indicators (20%)
    seed_amount_pattern: float = 0.05
    hold_vs_dump: float = 0.10
    network_connections: float = 0.05
    
    # Recent Activity (10%)
    momentum_score: float = 0.05
    last_7_days: float = 0.05

# ==================== COMPLETE HISTORICAL SCANNER ====================

class AnubisHistoricalScanner:
    """
    Complete historical scanner with full Anubis scoring integration
    """
    
    def __init__(self, db_pool):
        self.db = db_pool
        self.helius_key = os.getenv('HELIUS_API_KEY', 'dummy_key_for_testing')
        self.helius_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}"
        
        # Pump.fun program ID
        self.pump_program = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        
        # Scoring weights
        self.weights = AnubisWeights()
        
        # Track progress
        self.total_scanned = 0
        self.total_launches = 0
        self.unique_wallets = set()
        self.seen_signatures = set()
        
        # Cache for batch processing
        self.wallet_launches = {}  # wallet -> list of launches
        self.wallet_metrics = {}    # wallet -> calculated metrics
    
    async def scan_and_score(self, days_back: int = 30, batch_size: int = 1000):
        """
        Main entry point: Scan historical data and calculate all Anubis scores
        """
        print(f"🏛️ ANUBIS COMPLETE HISTORICAL SCANNER")
        print(f"   Scanning {days_back} days with full scoring")
        print("="*60)
        
        # Phase 1: Collect all historical launches
        print("\n📊 PHASE 1: Collecting historical launches...")
        await self._collect_historical_launches(days_back, batch_size)
        
        # Phase 2: Fetch market cap data for success determination
        print("\n💰 PHASE 2: Fetching market cap data...")
        await self._fetch_market_cap_data()
        
        # Phase 3: Calculate earnings and profits
        print("\n💵 PHASE 3: Calculating earnings and profits...")
        await self._calculate_earnings()
        
        # Phase 4: Analyze patterns for each wallet
        print("\n🔍 PHASE 4: Analyzing patterns for each wallet...")
        await self._analyze_wallet_patterns()
        
        # Phase 5: Calculate Anubis scores
        print("\n⚡ PHASE 5: Calculating Anubis scores...")
        await self._calculate_anubis_scores()
        
        # Phase 6: Store everything in database
        print("\n💾 PHASE 6: Storing complete profiles in database...")
        await self._store_complete_profiles()
        
        # Print summary
        await self._print_comprehensive_summary()
    
    async def _collect_historical_launches(self, days_back: int, batch_size: int):
        """
        Phase 1: Collect all token launches from blockchain
        """
        start_date = datetime.now() - timedelta(days=days_back)
        before_signature = None
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                try:
                    # Get batch of signatures
                    params = {"limit": batch_size, "commitment": "confirmed"}
                    if before_signature:
                        params["before"] = before_signature
                    
                    response = await client.post(
                        self.helius_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getSignaturesForAddress",
                            "params": [self.pump_program, params]
                        }
                    )
                    
                    if response.status_code != 200:
                        print(f"❌ API error: {response.status_code}")
                        break
                    
                    data = response.json()
                    signatures = data.get('result', [])
                    
                    if not signatures:
                        break
                    
                    # Process each signature
                    for sig_info in signatures:
                        signature = sig_info.get('signature')
                        block_time = sig_info.get('blockTime', 0)
                        
                        if signature in self.seen_signatures:
                            continue
                        self.seen_signatures.add(signature)
                        
                        # Check date range
                        if block_time > 0:
                            tx_date = datetime.fromtimestamp(block_time)
                            if tx_date < start_date:
                                return  # Reached target date
                        
                        # Process transaction
                        launch_data = await self._process_transaction(client, signature, tx_date if block_time > 0 else None)
                        if launch_data:
                            self._cache_launch_data(launch_data)
                            self.total_launches += 1
                            
                            if self.total_launches % 50 == 0:
                                print(f"   Processed {self.total_launches} launches from {len(self.unique_wallets)} wallets")
                    
                    before_signature = signatures[-1]['signature']
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Error: {e}")
                    await asyncio.sleep(5)
    
    async def _process_transaction(self, client: httpx.AsyncClient, signature: str, tx_date: datetime = None) -> Optional[Dict]:
        """
        Process a single transaction to extract launch data
        """
        try:
            # Fetch full transaction
            response = await client.post(
                self.helius_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        signature,
                        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                    ]
                }
            )
            
            if response.status_code != 200:
                return None
            
            tx_data = response.json()
            result = tx_data.get('result')
            
            if not result or result.get('meta', {}).get('err') is not None:
                return None
            
            # Check if it's a launch
            if not self._is_token_launch(result):
                return None
            
            # Extract comprehensive launch data
            return self._extract_comprehensive_launch_data(result, signature, tx_date)
            
        except Exception:
            return None
    
    def _is_token_launch(self, tx_result: dict) -> bool:
        """
        Determine if transaction is a token launch
        """
        logs = tx_result.get('meta', {}).get('logMessages', [])
        
        launch_indicators = [
            "Program log: Instruction: Create",
            "create_pump",
            "InitializeMint",
            "init_pump_token",
            "Creating pool",
            "Bonding curve created"
        ]
        
        for log in logs:
            if any(indicator in log for indicator in launch_indicators):
                return True
        
        return False
    
    def _extract_comprehensive_launch_data(self, tx_result: dict, signature: str, tx_date: datetime = None) -> dict:
        """
        Extract all relevant data from launch transaction
        """
        try:
            # Get account keys
            account_keys = tx_result.get('transaction', {}).get('message', {}).get('accountKeys', [])
            
            # Creator is fee payer
            creator = account_keys[0].get('pubkey') if account_keys else None
            
            # Find mint address
            mint = None
            for key in account_keys[1:6]:
                address = key.get('pubkey', '')
                if len(address) == 44 and address != self.pump_program and not address.startswith('11111'):
                    if key.get('writable', False):
                        mint = address
                        break
            
            # Calculate initial seed amount (SOL spent)
            pre_balances = tx_result.get('meta', {}).get('preBalances', [])
            post_balances = tx_result.get('meta', {}).get('postBalances', [])
            seed_amount = 0
            
            if pre_balances and post_balances:
                seed_amount = (pre_balances[0] - post_balances[0]) / 1e9  # Convert to SOL
            
            # Extract time data
            launch_hour = tx_date.hour if tx_date else 0
            launch_day = tx_date.weekday() if tx_date else 0
            is_weekend = launch_day >= 5 if tx_date else False
            
            # Determine time slot
            time_slot = self._determine_time_slot(launch_hour)
            
            return {
                'signature': signature,
                'mint': mint,
                'creator': creator,
                'launch_time': tx_date or datetime.now(),
                'launch_hour': launch_hour,
                'launch_day': launch_day,
                'is_weekend': is_weekend,
                'time_slot': time_slot,
                'seed_amount': seed_amount,
                'platform': 'pump_fun'
            }
            
        except Exception as e:
            print(f"Error extracting data: {e}")
            return None
    
    def _determine_time_slot(self, hour: int) -> str:
        """
        Determine which time slot a launch falls into
        """
        if 22 <= hour or hour < 2:
            return "ASIA_MORNING"
        elif 6 <= hour < 10:
            return "EU_MORNING"
        elif 13 <= hour < 17:
            return "US_MORNING"
        elif 0 <= hour < 4:
            return "PEAK_DEGEN"
        else:
            return "OTHER"
    
    def _cache_launch_data(self, launch_data: dict):
        """
        Cache launch data for batch processing
        """
        creator = launch_data['creator']
        if creator:
            self.unique_wallets.add(creator)
            
            if creator not in self.wallet_launches:
                self.wallet_launches[creator] = []
            
            self.wallet_launches[creator].append(launch_data)
    
    async def _fetch_market_cap_data(self):
        """
        Phase 2: Fetch market cap data for all tokens to determine success
        """
        print(f"   Fetching market cap data for {self.total_launches} tokens...")
        
        # Group tokens by wallet for batch processing
        success_count = 0
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for wallet, launches in self.wallet_launches.items():
                for launch in launches:
                    mint = launch['mint']
                    if not mint:
                        continue
                    
                    # Try Jupiter API for price
                    try:
                        response = await client.get(
                            f"https://price.jup.ag/v4/price?ids={mint}",
                            timeout=10.0
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if mint in data.get('data', {}):
                                market_cap = data['data'][mint].get('marketCap', 0)
                                launch['market_cap'] = market_cap
                                launch['is_success'] = market_cap > 100000
                                
                                if launch['is_success']:
                                    success_count += 1
                        
                        # Rate limiting
                        await asyncio.sleep(0.1)
                        
                    except Exception:
                        launch['market_cap'] = 0
                        launch['is_success'] = False
        
        print(f"   Found {success_count} successful tokens (>$100K mcap)")
    
    async def _calculate_earnings(self):
        """
        Phase 3: Calculate earnings and profits for each wallet
        """
        print(f"   Calculating earnings for {len(self.unique_wallets)} wallets...")
        
        for wallet, launches in self.wallet_launches.items():
            total_seed = sum(l.get('seed_amount', 0) for l in launches)
            successful_launches = [l for l in launches if l.get('is_success', False)]
            
            # Estimate earnings (simplified - in reality would need to track sells)
            # Assume successful tokens return 10x on average
            estimated_earnings = 0
            for launch in successful_launches:
                seed = launch.get('seed_amount', 0)
                mcap = launch.get('market_cap', 0)
                
                # Rough estimate: if mcap > 100k, assume 10x return minimum
                if mcap > 1000000:
                    estimated_earnings += seed * 50  # 50x for million+ mcap
                elif mcap > 100000:
                    estimated_earnings += seed * 10  # 10x for 100k+ mcap
            
            # Calculate profit
            estimated_profit = estimated_earnings - total_seed
            
            # Store in metrics
            if wallet not in self.wallet_metrics:
                self.wallet_metrics[wallet] = {}
            
            self.wallet_metrics[wallet]['total_seed_invested'] = total_seed
            self.wallet_metrics[wallet]['estimated_earnings'] = estimated_earnings
            self.wallet_metrics[wallet]['estimated_profit'] = estimated_profit
            self.wallet_metrics[wallet]['roi'] = (estimated_earnings / total_seed * 100) if total_seed > 0 else 0
    
    async def _analyze_wallet_patterns(self):
        """
        Phase 4: Analyze patterns for each wallet
        """
        print(f"   Analyzing patterns for {len(self.unique_wallets)} wallets...")
        
        for wallet, launches in self.wallet_launches.items():
            metrics = self.wallet_metrics.get(wallet, {})
            
            # Basic counts
            total_launches = len(launches)
            successful_launches = len([l for l in launches if l.get('is_success', False)])
            
            # Time patterns
            launch_hours = [l['launch_hour'] for l in launches]
            weekend_launches = len([l for l in launches if l['is_weekend']])
            
            # Time slot distribution
            asia_launches = len([l for l in launches if l['time_slot'] == 'ASIA_MORNING'])
            eu_launches = len([l for l in launches if l['time_slot'] == 'EU_MORNING'])
            us_launches = len([l for l in launches if l['time_slot'] == 'US_MORNING'])
            degen_launches = len([l for l in launches if l['time_slot'] == 'PEAK_DEGEN'])
            
            # Velocity calculation
            if len(launches) > 1:
                sorted_launches = sorted(launches, key=lambda x: x['launch_time'])
                time_diffs = []
                
                for i in range(1, len(sorted_launches)):
                    diff = (sorted_launches[i]['launch_time'] - sorted_launches[i-1]['launch_time']).total_seconds() / 60
                    time_diffs.append(diff)
                
                avg_time_between = np.mean(time_diffs) if time_diffs else 0
                min_time_between = min(time_diffs) if time_diffs else 0
                
                # Determine velocity type
                days_active = (sorted_launches[-1]['launch_time'] - sorted_launches[0]['launch_time']).days + 1
                avg_daily = total_launches / max(days_active, 1)
                
                if avg_daily > 5:
                    velocity_type = LaunchVelocity.SERIAL_SPAMMER.value
                elif avg_daily > 2:
                    velocity_type = LaunchVelocity.HIGH_FREQUENCY.value
                elif avg_daily > 0.5:
                    velocity_type = LaunchVelocity.MODERATE.value
                else:
                    velocity_type = LaunchVelocity.SELECTIVE.value
            else:
                avg_time_between = 0
                min_time_between = 0
                velocity_type = LaunchVelocity.SELECTIVE.value
            
            # Seed amount patterns
            seed_amounts = [l.get('seed_amount', 0) for l in launches]
            avg_seed = np.mean(seed_amounts) if seed_amounts else 0
            seed_variance = np.var(seed_amounts) if seed_amounts else 0
            
            # Success patterns
            success_rate = (successful_launches / total_launches * 100) if total_launches > 0 else 0
            
            # Best achievements
            best_mcap = max([l.get('market_cap', 0) for l in launches]) if launches else 0
            avg_mcap = np.mean([l.get('market_cap', 0) for l in launches]) if launches else 0
            
            # Store all metrics
            metrics.update({
                'total_launches': total_launches,
                'successful_launches': successful_launches,
                'success_rate': success_rate,
                'weekend_ratio': (weekend_launches / total_launches * 100) if total_launches > 0 else 0,
                'asia_session_ratio': (asia_launches / total_launches * 100) if total_launches > 0 else 0,
                'eu_session_ratio': (eu_launches / total_launches * 100) if total_launches > 0 else 0,
                'us_session_ratio': (us_launches / total_launches * 100) if total_launches > 0 else 0,
                'degen_ratio': (degen_launches / total_launches * 100) if total_launches > 0 else 0,
                'preferred_hours': list(set(launch_hours)),
                'velocity_type': velocity_type,
                'avg_time_between_launches': avg_time_between,
                'min_time_between_launches': min_time_between,
                'avg_seed_amount': avg_seed,
                'seed_variance': seed_variance,
                'best_mcap_achieved': best_mcap,
                'avg_mcap_achieved': avg_mcap,
                'first_seen': min(l['launch_time'] for l in launches),
                'last_active': max(l['launch_time'] for l in launches),
            })
            
            self.wallet_metrics[wallet] = metrics
    
    async def _calculate_anubis_scores(self):
        """
        Phase 5: Calculate comprehensive Anubis scores
        """
        print(f"   Calculating Anubis scores for {len(self.unique_wallets)} wallets...")
        
        for wallet, metrics in self.wallet_metrics.items():
            # Success score (0-100)
            success_score = min(metrics.get('success_rate', 0) * 2, 100)  # Double the rate, cap at 100
            
            # Earnings score (0-100) based on ROI
            roi = metrics.get('roi', 0)
            earnings_score = min(roi / 10, 100)  # 1000% ROI = 100 score
            
            # Scam score (0-100) - higher is worse
            scam_indicators = 0
            if metrics.get('velocity_type') == LaunchVelocity.SERIAL_SPAMMER.value:
                scam_indicators += 40
            if metrics.get('success_rate', 0) < 5 and metrics.get('total_launches', 0) > 10:
                scam_indicators += 30
            if metrics.get('min_time_between_launches', float('inf')) < 60:  # Less than 1 hour between launches
                scam_indicators += 30
            scam_score = min(scam_indicators, 100)
            
            # Time consistency score (0-100)
            # Lower variance in launch hours = more consistent
            hours = [l['launch_hour'] for l in self.wallet_launches.get(wallet, [])]
            hour_variance = np.var(hours) if hours else 12  # Default to medium variance
            time_consistency = max(0, 100 - (hour_variance * 4))  # Scale variance to 0-100
            
            # Calculate composite Anubis score
            anubis_score = (
                success_score * self.weights.success_rate +
                earnings_score * self.weights.total_earnings +
                (100 - scam_score) * self.weights.rug_rate +
                time_consistency * self.weights.time_consistency
            ) / (
                self.weights.success_rate + 
                self.weights.total_earnings + 
                self.weights.rug_rate + 
                self.weights.time_consistency
            )
            
            # Determine risk rating
            if scam_score > 80:
                risk_rating = "EXTREME"
            elif scam_score > 60:
                risk_rating = "HIGH"
            elif scam_score > 40:
                risk_rating = "MEDIUM"
            else:
                risk_rating = "LOW"
            
            # Determine developer tier
            if anubis_score > 80 and metrics.get('successful_launches', 0) > 5:
                developer_tier = "ELITE"
            elif anubis_score > 60 and metrics.get('successful_launches', 0) > 2:
                developer_tier = "PRO"
            elif anubis_score > 40:
                developer_tier = "AMATEUR"
            else:
                developer_tier = "SCAMMER"
            
            # Alert priority (1-10, 1 is highest)
            if developer_tier == "ELITE":
                alert_priority = 1
            elif developer_tier == "PRO":
                alert_priority = 3
            elif risk_rating == "EXTREME":
                alert_priority = 2  # Alert on likely scams too
            else:
                alert_priority = 5
            
            # Update metrics with scores
            metrics.update({
                'success_score': success_score,
                'earnings_score': earnings_score,
                'scam_score': scam_score,
                'time_consistency_score': time_consistency,
                'anubis_score': anubis_score,
                'risk_rating': risk_rating,
                'developer_tier': developer_tier,
                'alert_priority': alert_priority,
                'auto_alert': developer_tier in ["ELITE", "PRO"] or risk_rating == "EXTREME"
            })
    
    async def _store_complete_profiles(self):
        """
        Phase 6: Store all calculated data in database
        """
        print(f"   Storing profiles for {len(self.unique_wallets)} wallets...")
        
        async with self.db.acquire() as conn:
            # First store all launches
            for wallet, launches in self.wallet_launches.items():
                for launch in launches:
                    if launch.get('mint') and launch.get('creator'):
                        try:
                            await conn.execute("""
                                INSERT INTO token_launches 
                                (mint_address, creator_wallet, platform, launch_time, signature)
                                VALUES ($1, $2, $3, $4, $5)
                                ON CONFLICT (mint_address) DO NOTHING
                            """,
                                launch['mint'],
                                launch['creator'],
                                launch['platform'],
                                launch['launch_time'],
                                launch.get('signature')
                            )
                        except Exception as e:
                            print(f"Error storing launch: {e}")
            
            # Store wallet profiles with all Anubis metrics
            for wallet, metrics in self.wallet_metrics.items():
                try:
                    await conn.execute("""
                        INSERT INTO anubis_wallet_profiles (
                            wallet_address,
                            total_launches,
                            successful_launches,
                            success_rate,
                            scam_score,
                            success_score,
                            earnings_score,
                            time_consistency_score,
                            weekend_ratio,
                            asia_session_ratio,
                            eu_session_ratio,
                            us_session_ratio,
                            preferred_launch_hour,
                            launch_velocity_type,
                            avg_time_between_launches,
                            min_time_between_launches,
                            avg_seed_amount,
                            seed_variance,
                            best_mcap_achieved,
                            avg_mcap_achieved,
                            estimated_total_profit,
                            roi_percentage,
                            anubis_score,
                            risk_rating,
                            developer_tier,
                            alert_priority,
                            auto_alert,
                            first_seen,
                            last_active,
                            last_scored
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                            $21, $22, $23, $24, $25, $26, $27, $28, $29, NOW()
                        )
                        ON CONFLICT (wallet_address) DO UPDATE SET
                            total_launches = EXCLUDED.total_launches,
                            successful_launches = EXCLUDED.successful_launches,
                            success_rate = EXCLUDED.success_rate,
                            scam_score = EXCLUDED.scam_score,
                            anubis_score = EXCLUDED.anubis_score,
                            risk_rating = EXCLUDED.risk_rating,
                            developer_tier = EXCLUDED.developer_tier,
                            last_active = EXCLUDED.last_active,
                            last_scored = NOW()
                    """,
                        wallet,
                        metrics.get('total_launches', 0),
                        metrics.get('successful_launches', 0),
                        metrics.get('success_rate', 0),
                        metrics.get('scam_score', 0),
                        metrics.get('success_score', 0),
                        metrics.get('earnings_score', 0),
                        metrics.get('time_consistency_score', 0),
                        metrics.get('weekend_ratio', 0),
                        metrics.get('asia_session_ratio', 0),
                        metrics.get('eu_session_ratio', 0),
                        metrics.get('us_session_ratio', 0),
                        metrics.get('preferred_hours', []),
                        metrics.get('velocity_type', 'unknown'),
                        metrics.get('avg_time_between_launches', 0),
                        metrics.get('min_time_between_launches', 0),
                        metrics.get('avg_seed_amount', 0),
                        metrics.get('seed_variance', 0),
                        metrics.get('best_mcap_achieved', 0),
                        metrics.get('avg_mcap_achieved', 0),
                        metrics.get('estimated_profit', 0),
                        metrics.get('roi', 0),
                        metrics.get('anubis_score', 50),
                        metrics.get('risk_rating', 'UNKNOWN'),
                        metrics.get('developer_tier', 'UNKNOWN'),
                        metrics.get('alert_priority', 5),
                        metrics.get('auto_alert', False),
                        metrics.get('first_seen'),
                        metrics.get('last_active')
                    )
                except Exception as e:
                    print(f"Error storing profile for {wallet}: {e}")
    
    async def _print_comprehensive_summary(self):
        """
        Print comprehensive summary with all metrics
        """
        print("\n" + "="*60)
        print("🏛️ ANUBIS HISTORICAL SCAN COMPLETE")
        print("="*60)
        
        print(f"\n📊 SCAN STATISTICS:")
        print(f"   Total transactions scanned: {self.total_scanned:,}")
        print(f"   Token launches found: {self.total_launches:,}")
        print(f"   Unique wallets identified: {len(self.unique_wallets):,}")
        print(f"   Launch detection rate: {(self.total_launches/max(self.total_scanned,1)*100):.2f}%")
        
        # Calculate tier distribution
        tier_dist = {'ELITE': 0, 'PRO': 0, 'AMATEUR': 0, 'SCAMMER': 0}
        risk_dist = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'EXTREME': 0}
        
        for metrics in self.wallet_metrics.values():
            tier = metrics.get('developer_tier', 'UNKNOWN')
            risk = metrics.get('risk_rating', 'UNKNOWN')
            if tier in tier_dist:
                tier_dist[tier] += 1
            if risk in risk_dist:
                risk_dist[risk] += 1
        
        print(f"\n🎯 DEVELOPER TIER DISTRIBUTION:")
        for tier, count in tier_dist.items():
            percentage = (count / len(self.unique_wallets) * 100) if self.unique_wallets else 0
            print(f"   {tier}: {count} wallets ({percentage:.1f}%)")
        
        print(f"\n⚠️ RISK DISTRIBUTION:")
        for risk, count in risk_dist.items():
            percentage = (count / len(self.unique_wallets) * 100) if self.unique_wallets else 0
            print(f"   {risk}: {count} wallets ({percentage:.1f}%)")
        
        # Find top performers
        sorted_wallets = sorted(
            self.wallet_metrics.items(),
            key=lambda x: x[1].get('anubis_score', 0),
            reverse=True
        )
        
        print(f"\n🏆 TOP 5 WALLETS BY ANUBIS SCORE:")
        for i, (wallet, metrics) in enumerate(sorted_wallets[:5], 1):
            print(f"   {i}. {wallet[:8]}...")
            print(f"      Anubis Score: {metrics.get('anubis_score', 0):.1f}")
            print(f"      Tier: {metrics.get('developer_tier', 'UNKNOWN')}")
            print(f"      Launches: {metrics.get('total_launches', 0)}")
            print(f"      Success Rate: {metrics.get('success_rate', 0):.1f}%")
            print(f"      Est. Profit: {metrics.get('estimated_profit', 0):.2f} SOL")
        
        # Find serial launchers
        serial_launchers = [
            (w, m) for w, m in self.wallet_metrics.items()
            if m.get('velocity_type') == LaunchVelocity.SERIAL_SPAMMER.value
        ]
        
        print(f"\n🚨 SERIAL SPAMMERS DETECTED: {len(serial_launchers)}")
        for wallet, metrics in serial_launchers[:3]:
            print(f"   {wallet[:8]}... - {metrics.get('total_launches', 0)} launches")
        
        print("\n✅ Database has been populated with complete Anubis scoring data!")

# ==================== DATABASE SCHEMA ====================

ANUBIS_SCHEMA = """
-- Enhanced wallet profiles with complete Anubis scoring
CREATE TABLE IF NOT EXISTS anubis_wallet_profiles (
    wallet_address VARCHAR(64) PRIMARY KEY,
    
    -- Core Metrics
    total_launches INTEGER DEFAULT 0,
    successful_launches INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0,
    scam_score FLOAT DEFAULT 0,
    success_score FLOAT DEFAULT 0,
    earnings_score FLOAT DEFAULT 0,
    
    -- Time Patterns
    time_consistency_score FLOAT DEFAULT 0,
    weekend_ratio FLOAT DEFAULT 0,
    asia_session_ratio FLOAT DEFAULT 0,
    eu_session_ratio FLOAT DEFAULT 0,
    us_session_ratio FLOAT DEFAULT 0,
    preferred_launch_hour INTEGER[],
    
    -- Velocity Metrics
    launch_velocity_type VARCHAR(32),
    avg_time_between_launches FLOAT,
    min_time_between_launches FLOAT,
    
    -- Financial Metrics
    avg_seed_amount NUMERIC(18, 9),
    seed_variance FLOAT,
    best_mcap_achieved NUMERIC(20, 2),
    avg_mcap_achieved NUMERIC(20, 2),
    estimated_total_profit NUMERIC(20, 2),
    roi_percentage FLOAT,
    
    -- Anubis Scores
    anubis_score FLOAT DEFAULT 50,
    risk_rating VARCHAR(16),
    developer_tier VARCHAR(16),
    alert_priority INTEGER DEFAULT 5,
    auto_alert BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    first_seen TIMESTAMP,
    last_active TIMESTAMP,
    last_scored TIMESTAMP
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_anubis_score ON anubis_wallet_profiles(anubis_score DESC);
CREATE INDEX IF NOT EXISTS idx_developer_tier ON anubis_wallet_profiles(developer_tier);
CREATE INDEX IF NOT EXISTS idx_alert_priority ON anubis_wallet_profiles(alert_priority);
"""

async def connect_database():
    """Connect to DigitalOcean database"""
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        DB_HOST = os.getenv('DB_HOST')
        DB_PORT = os.getenv('DB_PORT', '25060')
        DB_NAME = os.getenv('DB_NAME', 'defaultdb')
        DB_USER = os.getenv('DB_USER', 'doadmin')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    
    print("Connecting to DigitalOcean database...")
    
    return await asyncpg.create_pool(
        DATABASE_URL,
        ssl='require',
        min_size=1,
        max_size=10
    )

async def main():
    """Run complete historical scanner with Anubis scoring"""
    print("🏛️ ANUBIS COMPLETE HISTORICAL SCANNER")
    print("="*60)
    
    # Get parameters
    days_back = int(os.getenv('SCAN_DAYS', 7))
    batch_size = int(os.getenv('BATCH_SIZE', 500))
    
    try:
        # Connect to database
        db = await connect_database()
        print("✅ Database connected!")
        
        # Create tables if needed
        async with db.acquire() as conn:
            await conn.execute(ANUBIS_SCHEMA)
            print("✅ Database schema ready!")
        
        # Create and run scanner
        scanner = AnubisHistoricalScanner(db)
        await scanner.scan_and_score(days_back, batch_size)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals():
            await db.close()

if __name__ == "__main__":
    asyncio.run(main())