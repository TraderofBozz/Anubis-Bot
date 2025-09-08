"""
Solana Memecoin Developer Wallet Aggregator
Pulls developer wallet data from multiple sources and identifies top creators
"""

import asyncio
import aiohttp
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict
import logging
from solana.publickey import PublicKey
from solana.rpc.async_api import AsyncClient
import pandas as pd
from collections import defaultdict
import re
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class DeveloperWallet:
    """Represents a memecoin developer wallet with metrics"""
    address: str
    tokens_created: int = 0
    successful_tokens: int = 0  # Tokens that reached $3M+ mcap
    total_volume: float = 0.0
    avg_peak_mcap: float = 0.0
    success_rate: float = 0.0
    last_token_date: Optional[str] = None
    data_sources: List[str] = None
    verified: bool = False
    risk_score: float = 0.0  # 0-100, higher = more risky
    
    def __post_init__(self):
        if self.data_sources is None:
            self.data_sources = []

class WalletAggregator:
    """Main aggregator class for collecting wallet data from multiple sources"""
    
    def __init__(self, rpc_url: str = "https://api.mainnet-beta.solana.com"):
        self.rpc_url = rpc_url
        self.client = AsyncClient(rpc_url)
        self.session = None
        self.db_conn = None
        self.wallets: Dict[str, DeveloperWallet] = {}
        
        # API configurations
        self.apis = {
            'dexscreener': 'https://api.dexscreener.com/latest',
            'birdeye': 'https://api.birdeye.so',
            'pump_fun': 'https://pump.fun/api',
            'solscan': 'https://api.solscan.io',
        }
        
        # Known pump.fun program addresses
        self.pump_fun_program = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ35BH7kftyPPP"
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        self.init_database()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
        if self.db_conn:
            self.db_conn.close()
            
    def init_database(self):
        """Initialize SQLite database for storing wallet data"""
        self.db_conn = sqlite3.connect('memecoin_developers.db')
        cursor = self.db_conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS developer_wallets (
                address TEXT PRIMARY KEY,
                tokens_created INTEGER,
                successful_tokens INTEGER,
                total_volume REAL,
                avg_peak_mcap REAL,
                success_rate REAL,
                last_token_date TEXT,
                data_sources TEXT,
                verified INTEGER,
                risk_score REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS token_launches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_address TEXT,
                developer_address TEXT,
                launch_date TIMESTAMP,
                peak_mcap REAL,
                current_mcap REAL,
                volume_24h REAL,
                is_rugpull INTEGER DEFAULT 0,
                FOREIGN KEY (developer_address) REFERENCES developer_wallets (address)
            )
        ''')
        
        self.db_conn.commit()
        
    async def fetch_dexscreener_data(self, limit: int = 100) -> List[Dict]:
        """Fetch top performing tokens from Dexscreener"""
        results = []
        try:
            # Get new pairs on Solana
            url = f"{self.apis['dexscreener']}/dex/pairs/solana"
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    for pair in pairs[:limit]:
                        if pair.get('chainId') == 'solana':
                            # Extract creator if available
                            results.append({
                                'token': pair.get('baseToken', {}).get('address'),
                                'mcap': float(pair.get('fdv', 0)),
                                'volume': float(pair.get('volume', {}).get('h24', 0)),
                                'created': pair.get('pairCreatedAt'),
                                'liquidity': float(pair.get('liquidity', {}).get('usd', 0))
                            })
            
            logger.info(f"Fetched {len(results)} tokens from Dexscreener")
            return results
            
        except Exception as e:
            logger.error(f"Error fetching Dexscreener data: {e}")
            return []
            
    async def fetch_pump_fun_creators(self) -> Set[str]:
        """Fetch recent token creators from pump.fun"""
        creators = set()
        try:
            # This would require actual pump.fun API access or on-chain monitoring
            # For now, we'll simulate with RPC calls
            
            # Get recent transactions to pump.fun program
            response = await self.client.get_signatures_for_address(
                PublicKey(self.pump_fun_program),
                limit=100
            )
            
            if response['result']:
                for sig_info in response['result']:
                    # Get transaction details
                    tx = await self.client.get_transaction(
                        sig_info['signature'],
                        encoding="json",
                        max_supported_transaction_version=0
                    )
                    
                    if tx['result'] and tx['result']['transaction']:
                        # Extract signer (creator)
                        message = tx['result']['transaction']['message']
                        if 'accountKeys' in message and len(message['accountKeys']) > 0:
                            creator = message['accountKeys'][0]
                            creators.add(creator)
                            
            logger.info(f"Found {len(creators)} unique creators from pump.fun")
            return creators
            
        except Exception as e:
            logger.error(f"Error fetching pump.fun creators: {e}")
            return set()
            
    async def analyze_wallet_history(self, wallet: str) -> DeveloperWallet:
        """Analyze a wallet's token creation history"""
        dev_wallet = DeveloperWallet(address=wallet)
        
        try:
            # Get wallet's transaction history
            response = await self.client.get_signatures_for_address(
                PublicKey(wallet),
                limit=1000
            )
            
            if response['result']:
                token_launches = []
                
                for sig_info in response['result']:
                    # Check if transaction involves pump.fun or token creation
                    tx = await self.client.get_transaction(
                        sig_info['signature'],
                        encoding="json",
                        max_supported_transaction_version=0
                    )
                    
                    if tx['result'] and self._is_token_creation(tx['result']):
                        token_launches.append({
                            'date': datetime.fromtimestamp(sig_info['blockTime']),
                            'signature': sig_info['signature']
                        })
                
                dev_wallet.tokens_created = len(token_launches)
                if token_launches:
                    dev_wallet.last_token_date = token_launches[0]['date'].isoformat()
                    
            # Calculate success metrics (would need price data)
            dev_wallet.success_rate = (
                dev_wallet.successful_tokens / dev_wallet.tokens_created 
                if dev_wallet.tokens_created > 0 else 0
            )
            
            return dev_wallet
            
        except Exception as e:
            logger.error(f"Error analyzing wallet {wallet}: {e}")
            return dev_wallet
            
    def _is_token_creation(self, transaction: Dict) -> bool:
        """Check if transaction is a token creation"""
        try:
            # Check for pump.fun program or SPL token program
            if 'transaction' in transaction:
                message = transaction['transaction']['message']
                instructions = message.get('instructions', [])
                
                for instruction in instructions:
                    program_id = instruction.get('programId')
                    # Check for token creation programs
                    if program_id in [
                        self.pump_fun_program,
                        'TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'  # SPL Token Program
                    ]:
                        return True
            return False
        except:
            return False
            
    async def fetch_trending_creators_gmgn(self) -> List[str]:
        """Simulate fetching trending creators from GMGN.ai"""
        # This would require GMGN API access
        # For demonstration, returning sample addresses
        trending = []
        
        try:
            # Simulate API call to GMGN
            # In reality, you'd need their API key
            logger.info("Fetching trending creators from GMGN.ai...")
            
            # Placeholder for actual API integration
            sample_wallets = [
                "HKiLftPVGDHYC3BS5FH1WVtXRpbdd7BhfYSQtZvPMjkk",
                "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
                "7Kn1Bkqz3KkKs8YF9RhAybKuZXLUNuKNQSHvNiGxVghZ"
            ]
            
            for wallet in sample_wallets:
                trending.append(wallet)
                
        except Exception as e:
            logger.error(f"Error fetching GMGN data: {e}")
            
        return trending
        
    async def scrape_dexscreener_top_traders(self, token_address: str) -> List[str]:
        """Scrape top traders for a specific token from Dexscreener"""
        traders = []
        
        try:
            # This would require web scraping as Dexscreener doesn't provide this via API
            # Using their website structure
            logger.info(f"Fetching top traders for token {token_address}")
            
            # Placeholder - in production, use playwright or selenium
            # to scrape the actual top traders tab
            
        except Exception as e:
            logger.error(f"Error scraping Dexscreener: {e}")
            
        return traders
        
    def calculate_risk_score(self, wallet: DeveloperWallet) -> float:
        """Calculate risk score for a developer wallet"""
        risk = 0.0
        
        # Factors that increase risk
        if wallet.tokens_created > 50:  # Too many tokens = likely scammer
            risk += 30
        if wallet.success_rate < 0.03:  # Less than 3% success
            risk += 40
        if wallet.tokens_created > 0 and wallet.successful_tokens == 0:
            risk += 30
            
        # Factors that decrease risk
        if wallet.successful_tokens >= 2:
            risk -= 20
        if wallet.success_rate > 0.1:  # More than 10% success
            risk -= 20
        if wallet.verified:
            risk -= 10
            
        return max(0, min(100, risk))
        
    async def aggregate_all_sources(self, limit: int = 150) -> List[DeveloperWallet]:
        """Main method to aggregate data from all sources"""
        all_wallets = set()
        
        logger.info("Starting wallet aggregation from all sources...")
        
        # 1. Fetch from pump.fun
        pump_creators = await self.fetch_pump_fun_creators()
        all_wallets.update(pump_creators)
        
        # 2. Fetch from GMGN trending
        gmgn_wallets = await self.fetch_trending_creators_gmgn()
        all_wallets.update(gmgn_wallets)
        
        # 3. Fetch successful tokens from Dexscreener
        dex_tokens = await self.fetch_dexscreener_data()
        
        # For each successful token, get top traders
        for token in dex_tokens[:20]:  # Limit to avoid rate limits
            if token['mcap'] > 1_000_000:  # Only tokens > $1M mcap
                traders = await self.scrape_dexscreener_top_traders(token['token'])
                all_wallets.update(traders)
                await asyncio.sleep(1)  # Rate limiting
                
        logger.info(f"Found {len(all_wallets)} unique wallets to analyze")
        
        # Analyze each wallet
        analyzed_wallets = []
        for wallet in list(all_wallets)[:limit]:
            dev_wallet = await self.analyze_wallet_history(wallet)
            dev_wallet.risk_score = self.calculate_risk_score(dev_wallet)
            analyzed_wallets.append(dev_wallet)
            
            # Save to database
            self.save_wallet_to_db(dev_wallet)
            
            # Rate limiting
            await asyncio.sleep(0.5)
            
        # Sort by success metrics
        analyzed_wallets.sort(
            key=lambda x: (x.successful_tokens, -x.risk_score), 
            reverse=True
        )
        
        return analyzed_wallets[:limit]
        
    def save_wallet_to_db(self, wallet: DeveloperWallet):
        """Save wallet data to database"""
        cursor = self.db_conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO developer_wallets 
            (address, tokens_created, successful_tokens, total_volume, 
             avg_peak_mcap, success_rate, last_token_date, data_sources, 
             verified, risk_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            wallet.address,
            wallet.tokens_created,
            wallet.successful_tokens,
            wallet.total_volume,
            wallet.avg_peak_mcap,
            wallet.success_rate,
            wallet.last_token_date,
            json.dumps(wallet.data_sources),
            int(wallet.verified),
            wallet.risk_score
        ))
        self.db_conn.commit()
        
    def export_to_csv(self, filename: str = "top_memecoin_developers.csv"):
        """Export database to CSV"""
        df = pd.read_sql_query(
            "SELECT * FROM developer_wallets ORDER BY successful_tokens DESC, risk_score ASC",
            self.db_conn
        )
        df.to_csv(filename, index=False)
        logger.info(f"Exported {len(df)} wallets to {filename}")
        return df

    def get_top_developers(self, limit: int = 100) -> List[DeveloperWallet]:
        """Get top developers from database"""
        cursor = self.db_conn.cursor()
        cursor.execute('''
            SELECT * FROM developer_wallets 
            WHERE risk_score < 70
            ORDER BY successful_tokens DESC, success_rate DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        developers = []
        
        for row in rows:
            dev = DeveloperWallet(
                address=row[0],
                tokens_created=row[1],
                successful_tokens=row[2],
                total_volume=row[3],
                avg_peak_mcap=row[4],
                success_rate=row[5],
                last_token_date=row[6],
                data_sources=json.loads(row[7]) if row[7] else [],
                verified=bool(row[8]),
                risk_score=row[9]
            )
            developers.append(dev)
            
        return developers

class WalletMonitor:
    """Real-time monitoring of identified developer wallets"""
    
    def __init__(self, aggregator: WalletAggregator):
        self.aggregator = aggregator
        self.monitored_wallets = set()
        self.alert_callbacks = []
        
    async def monitor_wallet_activity(self, wallet: str):
        """Monitor a specific wallet for new token launches"""
        logger.info(f"Starting monitoring for wallet: {wallet}")
        
        last_sig = None
        while True:
            try:
                # Get latest transactions
                response = await self.aggregator.client.get_signatures_for_address(
                    PublicKey(wallet),
                    limit=10,
                    until=last_sig
                )
                
                if response['result'] and len(response['result']) > 0:
                    new_txs = response['result']
                    
                    for tx in new_txs:
                        # Check if it's a token creation
                        tx_details = await self.aggregator.client.get_transaction(
                            tx['signature'],
                            encoding="json",
                            max_supported_transaction_version=0
                        )
                        
                        if tx_details['result'] and self.aggregator._is_token_creation(tx_details['result']):
                            await self.trigger_alert(wallet, tx['signature'])
                            
                    last_sig = new_txs[0]['signature']
                    
            except Exception as e:
                logger.error(f"Error monitoring wallet {wallet}: {e}")
                
            await asyncio.sleep(10)  # Check every 10 seconds
            
    async def trigger_alert(self, wallet: str, signature: str):
        """Trigger alert for new token launch"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'wallet': wallet,
            'signature': signature,
            'type': 'NEW_TOKEN_LAUNCH'
        }
        
        logger.warning(f"🚨 ALERT: New token launched by {wallet[:8]}...{wallet[-8:]}")
        logger.warning(f"Transaction: {signature}")
        
        # Execute callbacks
        for callback in self.alert_callbacks:
            await callback(alert)
            
    def add_alert_callback(self, callback):
        """Add a callback function for alerts"""
        self.alert_callbacks.append(callback)

async def main():
    """Main execution function"""
    async with WalletAggregator() as aggregator:
        # Step 1: Aggregate wallets from all sources
        print("🔍 Aggregating developer wallets from multiple sources...")
        top_developers = await aggregator.aggregate_all_sources(limit=150)
        
        # Step 2: Display results
        print(f"\n✅ Found {len(top_developers)} developer wallets\n")
        print("Top 10 Prolific Developers:")
        print("-" * 80)
        
        for i, dev in enumerate(top_developers[:10], 1):
            print(f"{i}. {dev.address}")
            print(f"   Tokens Created: {dev.tokens_created}")
            print(f"   Successful Tokens (>$3M): {dev.successful_tokens}")
            print(f"   Success Rate: {dev.success_rate:.2%}")
            print(f"   Risk Score: {dev.risk_score:.1f}/100")
            print(f"   Data Sources: {', '.join(dev.data_sources)}")
            print()
            
        # Step 3: Export to CSV
        df = aggregator.export_to_csv()
        print(f"\n📊 Exported {len(df)} wallets to CSV file")
        
        # Step 4: Optional - Start monitoring top wallets
        monitor_choice = input("\nStart real-time monitoring of top wallets? (y/n): ")
        if monitor_choice.lower() == 'y':
            monitor = WalletMonitor(aggregator)
            
            # Monitor top 5 developers
            monitoring_tasks = []
            for dev in top_developers[:5]:
                task = asyncio.create_task(monitor.monitor_wallet_activity(dev.address))
                monitoring_tasks.append(task)
                
            print(f"\n👀 Monitoring {len(monitoring_tasks)} wallets for new launches...")
            print("Press Ctrl+C to stop monitoring\n")
            
            try:
                await asyncio.gather(*monitoring_tasks)
            except KeyboardInterrupt:
                print("\n⏹️  Monitoring stopped")
                
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Program terminated by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise