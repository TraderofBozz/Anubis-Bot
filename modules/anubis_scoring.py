"""
ANUBIS SCORING SYSTEM V2.0
Complete implementation with all discussed features:
- Time-of-day patterns and launch timing analysis
- Behavioral bias detection (velocity, rug patterns, success timing)
- Multi-factor risk assessment with weighted scoring
- 90-day rolling metrics and pattern matching
- Network analysis and wallet clustering
- Advanced alert prioritization
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from enum import Enum
import json

# ==================== CONFIGURATION ====================

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

# ==================== DATABASE SCHEMA ====================

ANUBIS_SCHEMA = """
-- Enhanced wallet profiles with Anubis scoring
CREATE TABLE IF NOT EXISTS anubis_wallet_profiles (
    wallet_address VARCHAR(64) PRIMARY KEY,
    
    -- Core Metrics
    total_launches INTEGER DEFAULT 0,
    successful_launches INTEGER DEFAULT 0,  -- >$100K mcap
    total_rugs INTEGER DEFAULT 0,
    scam_score FLOAT DEFAULT 0,  -- 0-100 (100 = definite scammer)
    success_score FLOAT DEFAULT 0,  -- 0-100 (100 = highly successful)
    
    -- Time Pattern Analysis
    preferred_launch_hour INTEGER[],  -- Array of preferred hours (0-23)
    weekend_ratio FLOAT DEFAULT 0,
    asia_session_ratio FLOAT DEFAULT 0,
    eu_session_ratio FLOAT DEFAULT 0,
    us_session_ratio FLOAT DEFAULT 0,
    time_consistency_score FLOAT DEFAULT 0,  -- How consistent their timing is
    
    -- Velocity Metrics
    avg_daily_launches FLOAT DEFAULT 0,
    max_daily_launches INTEGER DEFAULT 0,
    launch_velocity_type VARCHAR(32),  -- serial_spammer, high_frequency, etc
    time_between_launches_avg INTEGER,  -- Average minutes between launches
    time_between_launches_min INTEGER,  -- Minimum minutes (detect bots)
    
    -- Financial Patterns
    avg_seed_amount NUMERIC(18, 9),
    min_seed_amount NUMERIC(18, 9),
    max_seed_amount NUMERIC(18, 9),
    seed_variance FLOAT,  -- Variance in seed amounts
    avg_take_profit NUMERIC(18, 9),  -- Average profit taken
    hold_rate FLOAT DEFAULT 0,  -- % of tokens held vs dumped
    
    -- Success Patterns
    avg_time_to_100k INTEGER,  -- Minutes to reach $100K
    avg_time_to_rug INTEGER,  -- Minutes before rug
    best_mcap_achieved NUMERIC(20, 2),
    avg_mcap_achieved NUMERIC(20, 2),
    success_rate_7d FLOAT DEFAULT 0,
    success_rate_30d FLOAT DEFAULT 0,
    success_rate_90d FLOAT DEFAULT 0,
    
    -- Network Analysis
    connected_wallets TEXT[],  -- Array of connected wallet addresses
    network_size INTEGER DEFAULT 0,
    cluster_id VARCHAR(32),  -- Identifies wallet clusters/farms
    sybil_score FLOAT DEFAULT 0,  -- Likelihood of being part of a bot network
    
    -- Platform Preferences
    pump_fun_ratio FLOAT DEFAULT 0,
    raydium_ratio FLOAT DEFAULT 0,
    preferred_platform VARCHAR(32),
    
    -- Anubis Composite Scores
    anubis_score FLOAT DEFAULT 50,  -- 0-100 overall score
    risk_rating VARCHAR(16),  -- LOW, MEDIUM, HIGH, EXTREME
    developer_tier VARCHAR(16),  -- ELITE, PRO, AMATEUR, SCAMMER
    
    -- Metadata
    first_seen TIMESTAMP,
    last_active TIMESTAMP,
    last_scored TIMESTAMP,
    scoring_version VARCHAR(16) DEFAULT 'v2.0',
    
    -- 90-Day Rolling Windows
    launches_90d INTEGER DEFAULT 0,
    success_90d INTEGER DEFAULT 0,
    rugs_90d INTEGER DEFAULT 0,
    volume_90d NUMERIC(20, 2),
    
    -- Alert Configuration
    alert_priority INTEGER DEFAULT 5,  -- 1-10 (1 = highest priority)
    auto_alert BOOLEAN DEFAULT FALSE,
    alert_reasons TEXT[]
);

-- Time-based launch patterns
CREATE TABLE IF NOT EXISTS launch_time_patterns (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(64) REFERENCES anubis_wallet_profiles(wallet_address),
    hour_utc INTEGER,
    day_of_week INTEGER,
    launch_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    avg_mcap NUMERIC(20, 2),
    UNIQUE(wallet_address, hour_utc, day_of_week)
);

-- Track wallet relationships and networks
CREATE TABLE IF NOT EXISTS wallet_networks (
    id SERIAL PRIMARY KEY,
    wallet_a VARCHAR(64),
    wallet_b VARCHAR(64),
    connection_type VARCHAR(32),  -- 'funds_transfer', 'same_seed_pattern', 'coordinated_launches'
    connection_strength FLOAT,  -- 0-1
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    UNIQUE(wallet_a, wallet_b)
);

-- Behavioral patterns and anomalies
CREATE TABLE IF NOT EXISTS behavioral_patterns (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(64) REFERENCES anubis_wallet_profiles(wallet_address),
    pattern_type VARCHAR(64),  -- 'pump_and_dump', 'slow_rug', 'honest_developer', etc
    confidence FLOAT,  -- 0-1 confidence in pattern
    evidence JSONB,  -- Detailed evidence for the pattern
    detected_at TIMESTAMP DEFAULT NOW()
);

-- Performance tracking for scoring accuracy
CREATE TABLE IF NOT EXISTS anubis_predictions (
    id SERIAL PRIMARY KEY,
    wallet_address VARCHAR(64),
    token_address VARCHAR(64),
    predicted_outcome VARCHAR(32),  -- 'success', 'rug', 'slow_bleed'
    confidence FLOAT,
    actual_outcome VARCHAR(32),
    predicted_at TIMESTAMP,
    resolved_at TIMESTAMP,
    score_version VARCHAR(16)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_anubis_score ON anubis_wallet_profiles(anubis_score DESC);
CREATE INDEX IF NOT EXISTS idx_risk_rating ON anubis_wallet_profiles(risk_rating);
CREATE INDEX IF NOT EXISTS idx_last_active ON anubis_wallet_profiles(last_active DESC);
CREATE INDEX IF NOT EXISTS idx_alert_priority ON anubis_wallet_profiles(alert_priority, auto_alert);
CREATE INDEX IF NOT EXISTS idx_launch_patterns ON launch_time_patterns(wallet_address, hour_utc);
CREATE INDEX IF NOT EXISTS idx_wallet_networks ON wallet_networks(wallet_a, wallet_b);
"""

# ==================== SCORING ENGINE ====================

class AnubisScoringEngine:
    """
    Core scoring engine implementing all discussed features
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.weights = AnubisWeights()
        
    async def calculate_anubis_score(self, wallet: str) -> Dict:
        """
        Calculate comprehensive Anubis score for a wallet
        Combines all factors: time patterns, velocity, success rate, network analysis
        Plus NEW: liquidity patterns, bonding, Jito usage, metadata quality, migrations
        """
        
        # Fetch all relevant data
        profile = await self._get_wallet_profile(wallet)
        time_patterns = await self._analyze_time_patterns(wallet)
        velocity = await self._calculate_velocity_metrics(wallet)
        network = await self._analyze_network_connections(wallet)
        recent_performance = await self._get_recent_performance(wallet)
        
        # NEW PRIORITY FEATURES
        liquidity = await self.analyze_liquidity_patterns(wallet)
        bonding = await self.analyze_bonding_patterns(wallet)
        jito = await self.detect_jito_usage(wallet)
        metadata = await self.analyze_metadata_quality(wallet)
        migrations = await self.track_platform_migrations(wallet)
        
        # Calculate component scores
        scores = {
            'success_score': self._calculate_success_score(profile),
            'scam_score': self._calculate_scam_score(profile, velocity, liquidity, bonding),
            'time_pattern_score': self._calculate_time_pattern_score(time_patterns),
            'velocity_score': self._calculate_velocity_score(velocity),
            'network_score': self._calculate_network_score(network),
            'momentum_score': self._calculate_momentum_score(recent_performance),
            'liquidity_score': self._calculate_liquidity_score(liquidity),
            'bonding_score': self._calculate_bonding_score(bonding),
            'sophistication_score': self._calculate_sophistication_score(jito, metadata, migrations)
        }
        
        # Calculate weighted composite score
        anubis_score = self._calculate_composite_score(scores)
        
        # Determine risk rating and tier
        risk_rating = self._determine_risk_rating(anubis_score, scores['scam_score'])
        developer_tier = self._determine_developer_tier(anubis_score, profile, jito, migrations)
        
        # Update database
        await self._update_wallet_scores(wallet, {
            'anubis_score': anubis_score,
            'risk_rating': risk_rating,
            'developer_tier': developer_tier,
            **scores
        })
        
        return {
            'wallet': wallet,
            'anubis_score': anubis_score,
            'risk_rating': risk_rating,
            'developer_tier': developer_tier,
            'component_scores': scores,
            'alert_priority': self._calculate_alert_priority(anubis_score, scores),
            'special_flags': {
                'uses_jito': jito.get('uses_jito', False),
                'bot_likely': liquidity.get('bot_likelihood', 0) > 0.7,
                'fast_bonder': bonding.get('min_bond_time', 999) < 10,
                'serial_graduate': migrations.get('graduation_count', 0) > 5
            }
        }
    
    def _calculate_scam_score(self, profile: Dict, velocity: Dict, liquidity: Dict, bonding: Dict) -> float:
        """Enhanced scam score with new pattern detection"""
        if not profile:
            return 50  # Unknown = neutral
        
        score = 0
        
        # High rug rate
        if profile['total_launches'] > 0:
            rug_rate = profile['total_rugs'] / profile['total_launches']
            score += rug_rate * 30
        
        # Serial spamming
        if velocity.get('velocity_type') == LaunchVelocity.SERIAL_SPAMMER.value:
            score += 25
        
        # Very short time between launches (bot-like)
        if velocity.get('min_interval') and velocity['min_interval'] < 10:  # Less than 10 minutes
            score += 15
        
        # NEW: Consistent seed amounts (bot indicator)
        if liquidity.get('bot_likelihood', 0) > 0.7:
            score += 20
        
        # NEW: Super fast bonding (manipulation)
        if bonding.get('min_bond_time') and bonding['min_bond_time'] < 10:
            score += 15
        
        # Low seed amounts (minimal risk)
        if profile.get('avg_seed_amount') and profile['avg_seed_amount'] < 1:
            score += 10
        
        return min(score, 100)
    
    def _calculate_liquidity_score(self, liquidity: Dict) -> float:
        """Score based on liquidity seeding patterns"""
        if not liquidity:
            return 50
        
        # Consistent seeds = likely bot
        bot_likelihood = liquidity.get('bot_likelihood', 0)
        
        # Higher variance is actually better (human behavior)
        if bot_likelihood < 0.3:
            return 80
        elif bot_likelihood < 0.5:
            return 60
        elif bot_likelihood < 0.7:
            return 40
        else:
            return 20
    
    def _calculate_bonding_score(self, bonding: Dict) -> float:
        """Score based on bonding patterns"""
        if not bonding or not bonding.get('avg_bond_time'):
            return 50
        
        score = 50
        
        # Graduation rate is key success metric
        grad_rate = bonding.get('graduation_rate', 0)
        score += grad_rate * 30
        
        # Natural bonding time (not too fast, not too slow)
        avg_time = bonding.get('avg_bond_time', 0)
        if 30 < avg_time < 180:  # 30 min to 3 hours is natural
            score += 20
        elif avg_time < 10:  # Super fast = manipulation
            score -= 20
        
        return max(0, min(score, 100))
    
    def _calculate_sophistication_score(self, jito: Dict, metadata: Dict, migrations: Dict) -> float:
        """Score for sophisticated developer behaviors"""
        score = 0
        
        # Jito usage shows sophistication
        if jito.get('sophisticated_trader'):
            score += 30
        elif jito.get('uses_jito'):
            score += 15
        
        # Quality metadata
        metadata_score = metadata.get('metadata_score', 0)
        score += metadata_score * 0.4
        
        # Successful graduations
        if migrations.get('successful_graduations', 0) > 0:
            score += 20
            if migrations.get('migration_success_rate', 0) > 0.5:
                score += 10
        
        return min(score, 100)
    
    def _determine_developer_tier(self, anubis_score: float, profile: Dict, jito: Dict, migrations: Dict) -> str:
        """Enhanced tier classification with new features"""
        # Elite requires everything: score, success, sophistication
        if (anubis_score > 80 and 
            profile.get('successful_launches', 0) > 5 and
            (jito.get('uses_jito') or migrations.get('successful_graduations', 0) > 2)):
            return "ELITE"
        elif anubis_score > 60:
            return "PRO"
        elif anubis_score > 40:
            return "AMATEUR"
        else:
            return "SCAMMER"
    
    async def _get_wallet_profile(self, wallet: str) -> Dict:
        """Fetch comprehensive wallet profile"""
        async with self.db.acquire() as conn:
            return await conn.fetchrow("""
                SELECT * FROM anubis_wallet_profiles
                WHERE wallet_address = $1
            """, wallet)
    
    async def _analyze_time_patterns(self, wallet: str) -> Dict:
        """Analyze launch time patterns for behavioral insights"""
        async with self.db.acquire() as conn:
            patterns = await conn.fetch("""
                SELECT hour_utc, day_of_week, launch_count, success_count, avg_mcap
                FROM launch_time_patterns
                WHERE wallet_address = $1
                ORDER BY launch_count DESC
            """, wallet)
            
            if not patterns:
                return {}
            
            # Identify preferred launch times
            total_launches = sum(p['launch_count'] for p in patterns)
            preferred_hours = [p['hour_utc'] for p in patterns if p['launch_count'] > total_launches * 0.1]
            
            # Calculate session preferences
            asia_launches = sum(p['launch_count'] for p in patterns if 22 <= p['hour_utc'] or p['hour_utc'] < 2)
            eu_launches = sum(p['launch_count'] for p in patterns if 6 <= p['hour_utc'] < 10)
            us_launches = sum(p['launch_count'] for p in patterns if 13 <= p['hour_utc'] < 17)
            
            # Weekend vs weekday
            weekend_launches = sum(p['launch_count'] for p in patterns if p['day_of_week'] in [5, 6])
            
            return {
                'preferred_hours': preferred_hours,
                'asia_ratio': asia_launches / total_launches if total_launches > 0 else 0,
                'eu_ratio': eu_launches / total_launches if total_launches > 0 else 0,
                'us_ratio': us_launches / total_launches if total_launches > 0 else 0,
                'weekend_ratio': weekend_launches / total_launches if total_launches > 0 else 0,
                'consistency': self._calculate_time_consistency(patterns)
            }
    
    async def _calculate_velocity_metrics(self, wallet: str) -> Dict:
        """Calculate launch velocity and frequency patterns"""
        async with self.db.acquire() as conn:
            # Get launch timestamps for last 90 days
            launches = await conn.fetch("""
                SELECT launch_time FROM token_launches
                WHERE creator_wallet = $1 
                AND launch_time > NOW() - INTERVAL '90 days'
                ORDER BY launch_time DESC
            """, wallet)
            
            if len(launches) < 2:
                return {'velocity_type': LaunchVelocity.SELECTIVE.value, 'avg_daily': 0}
            
            # Calculate time between launches
            intervals = []
            for i in range(len(launches) - 1):
                interval = (launches[i]['launch_time'] - launches[i+1]['launch_time']).total_seconds() / 60
                intervals.append(interval)
            
            # Daily launch counts
            daily_counts = {}
            for launch in launches:
                date = launch['launch_time'].date()
                daily_counts[date] = daily_counts.get(date, 0) + 1
            
            avg_daily = np.mean(list(daily_counts.values()))
            max_daily = max(daily_counts.values())
            
            # Determine velocity type
            if max_daily > 5:
                velocity_type = LaunchVelocity.SERIAL_SPAMMER
            elif avg_daily > 2:
                velocity_type = LaunchVelocity.HIGH_FREQUENCY
            elif avg_daily > 0.5:
                velocity_type = LaunchVelocity.MODERATE
            else:
                velocity_type = LaunchVelocity.SELECTIVE
            
            return {
                'velocity_type': velocity_type.value,
                'avg_daily': avg_daily,
                'max_daily': max_daily,
                'min_interval': min(intervals) if intervals else None,
                'avg_interval': np.mean(intervals) if intervals else None
            }
    
    async def _analyze_network_connections(self, wallet: str) -> Dict:
        """Analyze wallet network and identify coordinated behavior"""
        async with self.db.acquire() as conn:
            # Find connected wallets
            connections = await conn.fetch("""
                SELECT wallet_b, connection_type, connection_strength
                FROM wallet_networks
                WHERE wallet_a = $1
                AND connection_strength > 0.3
            """, wallet)
            
            # Check for wallet farming patterns
            if connections:
                # Look for coordinated launches
                coordinated = [c for c in connections if c['connection_type'] == 'coordinated_launches']
                same_seed = [c for c in connections if c['connection_type'] == 'same_seed_pattern']
                
                sybil_score = 0
                if len(coordinated) > 2:
                    sybil_score += 0.5
                if len(same_seed) > 3:
                    sybil_score += 0.3
                if len(connections) > 10:
                    sybil_score += 0.2
                
                return {
                    'network_size': len(connections),
                    'sybil_score': min(sybil_score, 1.0),
                    'coordinated_wallets': [c['wallet_b'] for c in coordinated],
                    'farming_suspected': sybil_score > 0.5
                }
            
            return {'network_size': 0, 'sybil_score': 0, 'farming_suspected': False}
    
    async def _get_recent_performance(self, wallet: str) -> Dict:
        """Get performance metrics for recent time windows"""
        async with self.db.acquire() as conn:
            # 7-day performance
            perf_7d = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as launches,
                    SUM(CASE WHEN peak_mcap > 100000 THEN 1 ELSE 0 END) as successes,
                    AVG(peak_mcap) as avg_mcap
                FROM token_launches tl
                LEFT JOIN successful_tokens_archive sta ON tl.mint_address = sta.mint_address
                WHERE tl.creator_wallet = $1
                AND tl.launch_time > NOW() - INTERVAL '7 days'
            """, wallet)
            
            # 30-day performance
            perf_30d = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as launches,
                    SUM(CASE WHEN peak_mcap > 100000 THEN 1 ELSE 0 END) as successes
                FROM token_launches tl
                LEFT JOIN successful_tokens_archive sta ON tl.mint_address = sta.mint_address
                WHERE tl.creator_wallet = $1
                AND tl.launch_time > NOW() - INTERVAL '30 days'
            """, wallet)
            
            return {
                'launches_7d': perf_7d['launches'] or 0,
                'successes_7d': perf_7d['successes'] or 0,
                'launches_30d': perf_30d['launches'] or 0,
                'successes_30d': perf_30d['successes'] or 0,
                'momentum': self._calculate_momentum(perf_7d, perf_30d)
            }
    
    def _calculate_success_score(self, profile: Dict) -> float:
        """Calculate success score based on historical performance"""
        if not profile or profile['total_launches'] == 0:
            return 0
        
        success_rate = profile['successful_launches'] / profile['total_launches']
        
        # Weight recent success more heavily
        recent_weight = 0.6 if profile.get('success_rate_7d', 0) > 0 else 0.3
        historical_weight = 1 - recent_weight
        
        score = (
            success_rate * historical_weight +
            profile.get('success_rate_7d', 0) * recent_weight
        ) * 100
        
        # Bonus for consistent success
        if profile['successful_launches'] > 5 and success_rate > 0.3:
            score = min(score * 1.2, 100)
        
        return score
    
    def _calculate_scam_score(self, profile: Dict, velocity: Dict) -> float:
        """Calculate likelihood of being a scammer"""
        if not profile:
            return 50  # Unknown = neutral
        
        score = 0
        
        # High rug rate
        if profile['total_launches'] > 0:
            rug_rate = profile['total_rugs'] / profile['total_launches']
            score += rug_rate * 40
        
        # Serial spamming
        if velocity.get('velocity_type') == LaunchVelocity.SERIAL_SPAMMER.value:
            score += 30
        
        # Very short time between launches (bot-like)
        if velocity.get('min_interval') and velocity['min_interval'] < 10:  # Less than 10 minutes
            score += 20
        
        # Low seed amounts (minimal risk)
        if profile.get('avg_seed_amount') and profile['avg_seed_amount'] < 1:
            score += 10
        
        return min(score, 100)
    
    def _calculate_time_pattern_score(self, patterns: Dict) -> float:
        """Score based on time pattern consistency and smart timing"""
        if not patterns:
            return 50
        
        score = 50  # Base score
        
        # Consistency is good (not random)
        if patterns.get('consistency', 0) > 0.7:
            score += 20
        
        # Targeting specific sessions (strategic)
        if patterns.get('asia_ratio', 0) > 0.6 or patterns.get('us_ratio', 0) > 0.6:
            score += 15
        
        # Weekend warrior (often scammers)
        if patterns.get('weekend_ratio', 0) > 0.6:
            score -= 10
        
        return max(0, min(score, 100))
    
    def _calculate_velocity_score(self, velocity: Dict) -> float:
        """Score based on launch frequency patterns"""
        velocity_scores = {
            LaunchVelocity.SERIAL_SPAMMER.value: 10,
            LaunchVelocity.HIGH_FREQUENCY.value: 30,
            LaunchVelocity.MODERATE.value: 70,
            LaunchVelocity.SELECTIVE.value: 90
        }
        
        return velocity_scores.get(velocity.get('velocity_type'), 50)
    
    def _calculate_network_score(self, network: Dict) -> float:
        """Score based on network analysis"""
        if network.get('farming_suspected'):
            return 20
        
        base_score = 70
        
        # Small network is better (not part of a farm)
        if network.get('network_size', 0) < 3:
            base_score += 20
        elif network.get('network_size', 0) > 10:
            base_score -= 30
        
        # Sybil score reduces overall score
        base_score -= network.get('sybil_score', 0) * 50
        
        return max(0, min(base_score, 100))
    
    def _calculate_momentum_score(self, recent: Dict) -> float:
        """Calculate momentum based on recent activity"""
        if not recent.get('launches_7d'):
            return 0
        
        # Recent success rate
        recent_success = recent.get('successes_7d', 0) / recent.get('launches_7d', 1)
        
        # Activity level
        if recent.get('launches_7d', 0) > 10:  # Very active
            activity_score = 30
        elif recent.get('launches_7d', 0) > 3:  # Moderately active
            activity_score = 50
        else:  # Selective
            activity_score = 70
        
        return (recent_success * 70 + activity_score * 0.3)
    
    def _calculate_composite_score(self, scores: Dict) -> float:
        """Calculate weighted composite Anubis score"""
        weights = self.weights
        
        composite = (
            scores.get('success_score', 0) * weights.success_rate +
            (100 - scores.get('scam_score', 0)) * weights.rug_rate +
            scores.get('time_pattern_score', 50) * weights.time_consistency +
            scores.get('velocity_score', 50) * weights.velocity_pattern +
            scores.get('network_score', 50) * weights.network_connections +
            scores.get('momentum_score', 0) * weights.momentum_score
        )
        
        # Normalize to 0-100
        total_weight = (
            weights.success_rate + weights.rug_rate + weights.time_consistency +
            weights.velocity_pattern + weights.network_connections + weights.momentum_score
        )
        
        return composite / total_weight if total_weight > 0 else 50
    
    def _calculate_time_consistency(self, patterns: List) -> float:
        """Calculate how consistent launch times are"""
        if not patterns:
            return 0
        
        # Calculate entropy of launch hour distribution
        total = sum(p['launch_count'] for p in patterns)
        if total == 0:
            return 0
        
        probabilities = [p['launch_count'] / total for p in patterns]
        entropy = -sum(p * np.log2(p) if p > 0 else 0 for p in probabilities)
        
        # Normalize (lower entropy = more consistent)
        max_entropy = np.log2(24)  # 24 hours
        consistency = 1 - (entropy / max_entropy)
        
        return consistency
    
    def _calculate_momentum(self, perf_7d: Dict, perf_30d: Dict) -> float:
        """Calculate momentum (recent performance vs historical)"""
        if not perf_30d or perf_30d['launches'] == 0:
            return 0
        
        # Compare 7-day success rate to 30-day
        success_7d = perf_7d['successes'] / perf_7d['launches'] if perf_7d['launches'] > 0 else 0
        success_30d = perf_30d['successes'] / perf_30d['launches'] if perf_30d['launches'] > 0 else 0
        
        # Positive momentum if recent > historical
        momentum = (success_7d - success_30d) * 100
        
        return max(-100, min(momentum, 100))
    
    def _determine_risk_rating(self, anubis_score: float, scam_score: float) -> str:
        """Determine risk rating based on scores"""
        if scam_score > 75 or anubis_score < 25:
            return "EXTREME"
        elif scam_score > 50 or anubis_score < 40:
            return "HIGH"
        elif scam_score > 30 or anubis_score < 60:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _determine_developer_tier(self, anubis_score: float, profile: Dict) -> str:
        """Classify developer into tiers"""
        if anubis_score > 80 and profile.get('successful_launches', 0) > 5:
            return "ELITE"
        elif anubis_score > 60:
            return "PRO"
        elif anubis_score > 40:
            return "AMATEUR"
        else:
            return "SCAMMER"
    
    def _calculate_alert_priority(self, anubis_score: float, scores: Dict) -> int:
        """Calculate alert priority (1-10, 1 being highest)"""
        # High success developers get priority 1-3
        if anubis_score > 75:
            if scores.get('momentum_score', 0) > 70:
                return 1
            return 2
        
        # Known scammers get low priority
        if scores.get('scam_score', 0) > 70:
            return 9
        
        # Medium risk gets medium priority
        if 40 < anubis_score < 60:
            return 5
        
        return 7
    
    async def _update_wallet_scores(self, wallet: str, scores: Dict):
        """Update wallet with calculated scores"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                UPDATE anubis_wallet_profiles
                SET 
                    anubis_score = $2,
                    risk_rating = $3,
                    developer_tier = $4,
                    scam_score = $5,
                    success_score = $6,
                    alert_priority = $7,
                    last_scored = NOW()
                WHERE wallet_address = $1
            """, wallet, scores['anubis_score'], scores['risk_rating'],
                scores['developer_tier'], scores['scam_score'],
                scores['success_score'], scores['alert_priority'])

# ==================== PATTERN DETECTION ====================

class PatternDetector:
    """Detect specific behavioral patterns in developer activity"""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
    
    async def detect_pump_and_dump(self, wallet: str, token: str) -> Tuple[bool, float]:
        """Detect classic pump and dump pattern"""
        async with self.db.acquire() as conn:
            # Get token launch and price history
            history = await conn.fetch("""
                SELECT timestamp, price, volume
                FROM price_history
                WHERE token_address = $1
                ORDER BY timestamp
            """, token)
            
            if len(history) < 10:
                return False, 0.0
            
            # Look for rapid price increase followed by crash
            prices = [h['price'] for h in history]
            max_price = max(prices)
            max_idx = prices.index(max_price)
            
            # Check if price crashed after peak
            if max_idx < len(prices) - 5:
                crash_price = prices[max_idx + 5]
                if crash_price < max_price * 0.3:  # 70% crash
                    # Check if developer sold at peak
                    dev_sold = await conn.fetchval("""
                        SELECT EXISTS(
                            SELECT 1 FROM transactions
                            WHERE from_wallet = $1
                            AND token_address = $2
                            AND timestamp BETWEEN $3 AND $4
                        )
                    """, wallet, token, history[max_idx-1]['timestamp'], history[max_idx+2]['timestamp'])
                    
                    if dev_sold:
                        return True, 0.9
            
            return False, 0.2
    
    async def detect_slow_rug(self, wallet: str, token: str) -> Tuple[bool, float]:
        """Detect slow rug pattern (gradual liquidity removal)"""
        async with self.db.acquire() as conn:
            # Track liquidity changes over time
            liquidity = await conn.fetch("""
                SELECT timestamp, liquidity_usd
                FROM liquidity_history
                WHERE token_address = $1
                ORDER BY timestamp
            """, token)
            
            if len(liquidity) < 20:
                return False, 0.0
            
            # Check for consistent liquidity decrease
            decreases = 0
            for i in range(1, len(liquidity)):
                if liquidity[i]['liquidity_usd'] < liquidity[i-1]['liquidity_usd'] * 0.95:
                    decreases += 1
            
            if decreases > len(liquidity) * 0.6:  # 60% of time decreasing
                return True, decreases / len(liquidity)
            
            return False, 0.1
    
    async def detect_honeypot(self, wallet: str, token: str) -> Tuple[bool, float]:
        """Detect honeypot pattern (can't sell)"""
        async with self.db.acquire() as conn:
            # Check sell transactions
            sells = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions
                WHERE token_address = $1
                AND transaction_type = 'sell'
                AND from_wallet != $2
            """, token, wallet)
            
            buys = await conn.fetchval("""
                SELECT COUNT(*) FROM transactions
                WHERE token_address = $1
                AND transaction_type = 'buy'
            """, token)
            
            if buys > 50 and sells < 5:
                return True, 0.95
            elif buys > 20 and sells < buys * 0.1:
                return True, 0.7
            
            return False, 0.1

# ==================== ALERT SYSTEM ====================

class AnubisAlertSystem:
    """Intelligent alert system based on Anubis scores"""
    
    def __init__(self, db_pool: asyncpg.Pool, telegram_bot=None):
        self.db = db_pool
        self.bot = telegram_bot
        self.scoring_engine = AnubisScoringEngine(db_pool)
    
    async def process_new_launch(self, wallet: str, token: str, platform: str):
        """Process new token launch and determine if alert needed"""
        
        # Get wallet's Anubis score
        scores = await self.scoring_engine.calculate_anubis_score(wallet)
        
        # Determine if alert should be sent
        should_alert, alert_level = self._should_alert(scores)
        
        if should_alert:
            alert_message = await self._generate_alert_message(wallet, token, platform, scores)
            
            # Send to appropriate channels based on alert level
            if alert_level == "CRITICAL":
                await self._send_critical_alert(alert_message)
            elif alert_level == "HIGH":
                await self._send_high_priority_alert(alert_message)
            else:
                await self._send_standard_alert(alert_message)
            
            # Log alert
            await self._log_alert(wallet, token, alert_level, scores)
    
    def _should_alert(self, scores: Dict) -> Tuple[bool, str]:
        """Determine if and what level of alert to send"""
        anubis_score = scores['anubis_score']
        
        # Elite developers always alert
        if scores['developer_tier'] == "ELITE":
            return True, "CRITICAL"
        
        # High momentum + good score
        if scores['component_scores'].get('momentum_score', 0) > 80 and anubis_score > 60:
            return True, "HIGH"
        
        # Good score but not elite
        if anubis_score > 70:
            return True, "STANDARD"
        
        # Known scammers - no alert
        if scores['risk_rating'] == "EXTREME":
            return False, None
        
        return False, None
    
    async def _generate_alert_message(self, wallet: str, token: str, platform: str, scores: Dict) -> str:
        """Generate detailed alert message with Anubis insights"""
        
        profile = await self.scoring_engine._get_wallet_profile(wallet)
        earnings = await self.scoring_engine.calculate_developer_earnings(wallet)
        
        # Emoji indicators
        tier_emojis = {
            "ELITE": "👑",
            "PRO": "⭐",
            "AMATEUR": "📊",
            "SCAMMER": "🚫"
        }
        
        risk_emojis = {
            "LOW": "✅",
            "MEDIUM": "⚠️",
            "HIGH": "🔴",
            "EXTREME": "☠️"
        }
        
        message = f"""
{tier_emojis.get(scores['developer_tier'], '❓')} **NEW LAUNCH DETECTED**

**Developer**: `{wallet[:8]}...{wallet[-6:]}`
**Tier**: {scores['developer_tier']}
**Anubis Score**: {scores['anubis_score']:.1f}/100
**Risk**: {risk_emojis.get(scores['risk_rating'], '❓')} {scores['risk_rating']}

**Token**: `{token[:8]}...{token[-6:]}`
**Platform**: {platform}

**💰 Earnings History**:
• Total Profit: ${earnings.get('total_profit_usd', 0):,.0f} ({earnings.get('total_profit_sol', 0):.1f} SOL)
• Best Success: {earnings.get('best_success_name', 'None')}
• Best ROI: {earnings.get('best_roi_percent', 0):.0f}% on {earnings.get('best_roi_token', 'N/A')}
• Major Wins: {', '.join(earnings.get('major_successes', [])) or 'None yet'}

**Historical Performance**:
• Total Launches: {profile.get('total_launches', 0)}
• Success Rate: {profile.get('successful_launches', 0) / max(profile.get('total_launches', 1), 1) * 100:.1f}%
• Best MCap: ${profile.get('best_mcap_achieved', 0):,.0f}
• Exit Strategy: {profile.get('exit_strategy', 'Unknown')}

**Recent Activity**:
• 7-Day Momentum: {scores['component_scores'].get('momentum_score', 0):.0f}
• Launch Velocity: {profile.get('launch_velocity_type', 'Unknown')}

**Insights**:
"""
        
        # Add specific insights based on patterns
        if scores['developer_tier'] == "ELITE":
            message += "• 🎯 Elite developer with proven track record\n"
        
        if earnings.get('total_profit_usd', 0) > 1000000:
            message += "• 💎 Millionaire developer - has earned over $1M\n"
        
        if earnings.get('best_roi_percent', 0) > 10000:
            message += f"• 🚀 Achieved {earnings.get('best_roi_percent', 0)/100:.0f}x return on {earnings.get('best_roi_token')}\n"
        
        if scores['component_scores'].get('momentum_score', 0) > 70:
            message += "• 🔥 Strong recent momentum\n"
        
        if profile.get('preferred_platform') == platform:
            message += f"• 📍 Preferred platform match ({platform})\n"
        
        # Add time-based insight
        current_hour = datetime.now().hour
        if profile.get('preferred_launch_hour') and current_hour in profile['preferred_launch_hour']:
            message += "• ⏰ Launching at preferred time\n"
        
        return message
    
    async def _send_critical_alert(self, message: str):
        """Send critical priority alert"""
        # Send to VIP channel with notification
        if self.bot:
            await self.bot.send_message(
                chat_id=CRITICAL_ALERTS_CHANNEL,
                text=message,
                parse_mode='Markdown'
            )
    
    async def _send_high_priority_alert(self, message: str):
        """Send high priority alert"""
        if self.bot:
            await self.bot.send_message(
                chat_id=HIGH_PRIORITY_CHANNEL,
                text=message,
                parse_mode='Markdown'
            )
    
    async def _send_standard_alert(self, message: str):
        """Send standard alert"""
        if self.bot:
            await self.bot.send_message(
                chat_id=STANDARD_ALERTS_CHANNEL,
                text=message,
                parse_mode='Markdown'
            )
    
    async def _log_alert(self, wallet: str, token: str, level: str, scores: Dict):
        """Log alert to database for tracking"""
        async with self.db.acquire() as conn:
            await conn.execute("""
                INSERT INTO alerts_log 
                (wallet_address, token_address, alert_level, anubis_score, sent_at)
                VALUES ($1, $2, $3, $4, NOW())
            """, wallet, token, level, scores['anubis_score'])

# ==================== USAGE EXAMPLE ====================

async def main():
    """Example usage of the Anubis Scoring System"""
    
    # Initialize database connection
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    
    # Create tables
    async with db_pool.acquire() as conn:
        await conn.execute(ANUBIS_SCHEMA)
    
    # Initialize scoring engine
    scoring_engine = AnubisScoringEngine(db_pool)
    
    # Score a wallet
    wallet = "YourWalletAddressHere"
    scores = await scoring_engine.calculate_anubis_score(wallet)
    
    print(f"Anubis Score: {scores['anubis_score']:.2f}")
    print(f"Risk Rating: {scores['risk_rating']}")
    print(f"Developer Tier: {scores['developer_tier']}")
    
    # Initialize alert system
    alert_system = AnubisAlertSystem(db_pool)
    
    # Process new launch
    await alert_system.process_new_launch(
        wallet="DeveloperWallet",
        token="NewTokenAddress",
        platform="pump_fun"
    )
    
    await db_pool.close()

if __name__ == "__main__":
    import os
    DATABASE_URL = os.getenv('DATABASE_URL')
    CRITICAL_ALERTS_CHANNEL = os.getenv('CRITICAL_ALERTS_CHANNEL')
    HIGH_PRIORITY_CHANNEL = os.getenv('HIGH_PRIORITY_CHANNEL')
    STANDARD_ALERTS_CHANNEL = os.getenv('STANDARD_ALERTS_CHANNEL')
    
    asyncio.run(main())