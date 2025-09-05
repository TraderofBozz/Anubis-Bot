"""
Pump.fun Token Launch Monitor
Real-time monitoring with NO hardcoded data
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, List
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.signature import Signature
from loguru import logger
import base58

class PumpFunMonitor:
    """Monitor Pump.fun for new token launches"""
    
    PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
    
    def __init__(self, rpc_url: str, db):
        self.rpc_url = rpc_url
        self.client = AsyncClient(rpc_url)
        self.db = db
        self.monitoring = False
        self.last_signature = None
        
    async def start_monitoring(self):
        """Start monitoring for new launches"""
        self.monitoring = True
        logger.info("Starting Pump.fun monitoring...")
        
        while self.monitoring:
            try:
                await self.check_new_launches()
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
    
    async def check_new_launches(self):
        """Check for new token launches"""
        try:
            # Get recent signatures for Pump.fun program
            response = await self.client.get_signatures_for_address(
                Pubkey.from_string(self.PUMP_FUN_PROGRAM),
                limit=20,
                before=self.last_signature
            )
            
            if not response.value:
                return
            
            # Process new transactions
            for sig_info in reversed(response.value):
                if await self.is_token_creation(sig_info.signature):
                    await self.process_new_launch(sig_info.signature)
            
            # Update last signature
            if response.value:
                self.last_signature = response.value[0].signature
                
        except Exception as e:
            logger.error(f"Error checking launches: {e}")
    
    async def is_token_creation(self, signature: Signature) -> bool:
        """Check if transaction is a token creation"""
        try:
            tx = await self.client.get_transaction(
                signature,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not tx.value:
                return False
            
            # Look for token creation instructions
            # This is simplified - you'd need to parse the actual instruction data
            meta = tx.value.transaction.meta
            if meta and meta.log_messages:
                for log in meta.log_messages:
                    if "CreateToken" in log or "InitializeMint" in log:
                        return True
                        
            return False
            
        except Exception as e:
            logger.error(f"Error checking transaction {signature}: {e}")
            return False
    
    async def process_new_launch(self, signature: Signature):
        """Process a new token launch"""
        try:
            tx = await self.client.get_transaction(
                signature,
                encoding="jsonParsed",
                max_supported_transaction_version=0
            )
            
            if not tx.value:
                return
            
            # Extract launch details
            launch_data = await self.extract_launch_data(tx.value, str(signature))
            
            if launch_data:
                # Record to database
                await self.db.record_launch(launch_data)
                
                # Update developer profile
                await self.update_developer_profile(launch_data['creator_wallet'])
                
                logger.info(f"New launch detected: {launch_data['token_symbol']} by {launch_data['creator_wallet'][:8]}...")
                
                # Trigger alerts for users tracking this developer
                await self.trigger_alerts(launch_data)
                
        except Exception as e:
            logger.error(f"Error processing launch: {e}")
    
    async def extract_launch_data(self, transaction, signature: str) -> Optional[Dict]:
        """Extract launch data from transaction"""
        try:
            # Get the creator (first signer)
            creator = None
            if transaction.transaction.message.account_keys:
                creator = str(transaction.transaction.message.account_keys[0].pubkey)
            
            # Get block time
            launch_time = datetime.fromtimestamp(transaction.block_time) if transaction.block_time else datetime.utcnow()
            
            # Extract token details from parsed instructions
            # This is simplified - you'd need proper instruction parsing
            token_data = {
                'creator_wallet': creator,
                'launch_signature': signature,
                'launch_time': launch_time,
                'mint_address': None,  # Extract from instructions
                'token_name': None,    # Extract from metadata
                'token_symbol': None,  # Extract from metadata
                'initial_supply': None,
                'initial_liquidity_sol': None
            }
            
            # Parse instructions to get mint address and details
            for instruction in transaction.transaction.message.instructions:
                # This would need actual instruction parsing logic
                pass
            
            return token_data if token_data['creator_wallet'] else None
            
        except Exception as e:
            logger.error(f"Error extracting launch data: {e}")
            return None
    
    async def update_developer_profile(self, wallet_address: str):
        """Update developer statistics"""
        try:
            # Get current profile
            developer = await self.db.get_developer(wallet_address)
            
            if developer:
                # Update launch count
                await self.db.upsert_developer(
                    wallet_address,
                    total_launches=developer['total_launches'] + 1,
                    last_launch_time=datetime.utcnow()
                )
            else:
                # New developer
                await self.db.upsert_developer(
                    wallet_address,
                    total_launches=1,
                    first_seen=datetime.utcnow(),
                    last_launch_time=datetime.utcnow()
                )
                
        except Exception as e:
            logger.error(f"Error updating developer profile: {e}")
    
    async def trigger_alerts(self, launch_data: Dict):
        """Trigger alerts for users tracking this developer"""
        # This will be connected to the Telegram bot
        pass
    
    async def analyze_developer_patterns(self, wallet_address: str) -> Dict:
        """Analyze patterns for a developer - based on actual data only"""
        try:
            # Get all launches by this developer
            async with self.db.acquire() as conn:
                launches = await conn.fetch("""
                    SELECT * FROM token_launches
                    WHERE creator_wallet = $1
                    ORDER BY launch_time DESC
                """, wallet_address)
                
                if not launches:
                    return {'status': 'no_data'}
                
                # Analyze patterns from ACTUAL data
                patterns = {
                    'total_launches': len(launches),
                    'launch_times': [],
                    'launch_days': [],
                    'avg_liquidity': 0,
                    'successful_count': 0
                }
                
                total_liquidity = 0
                for launch in launches:
                    # Extract patterns
                    patterns['launch_times'].append(launch['launch_time'].hour)
                    patterns['launch_days'].append(launch['launch_time'].strftime('%A'))
                    
                    if launch['initial_liquidity_sol']:
                        total_liquidity += float(launch['initial_liquidity_sol'])
                    
                    if launch['final_outcome'] == 'success':
                        patterns['successful_count'] += 1
                
                # Calculate averages
                if patterns['total_launches'] > 0:
                    patterns['avg_liquidity'] = total_liquidity / patterns['total_launches']
                    patterns['success_rate'] = (patterns['successful_count'] / patterns['total_launches']) * 100
                
                # Find most common launch hour
                if patterns['launch_times']:
                    from collections import Counter
                    patterns['preferred_hour'] = Counter(patterns['launch_times']).most_common(1)[0][0]
                    patterns['preferred_day'] = Counter(patterns['launch_days']).most_common(1)[0][0]
                
                return patterns
                
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return {'status': 'error'}
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        logger.info("Pump.fun monitoring stopped")