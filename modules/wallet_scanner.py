"""
modules/wallet_scanner.py
Complete implementation for historical scanning and real-time monitoring
"""

import asyncio
import asyncpg
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import httpx
from websockets import connect
from loguru import logger
import base58
from modules.anubis_scoring import AnubisScoringEngine, AnubisAlertSystem
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class WalletScanner:
    """
    Combined scanner for historical data and real-time monitoring
    Handles Pump.fun and Raydium LaunchLab (includes LetsBonk.fun)
    """
    
    def __init__(self, db):
        self.db = db
        self.helius_key = os.getenv('HELIUS_API_KEY', 'dummy_key_for_testing')
        
        # RPC endpoints
        self.helius_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}"
        self.helius_ws_url = f"wss://mainnet.helius-rpc.com/?api-key={self.helius_key}"
        
        # Anubis Scoring System
        self.scoring_engine = None
        self.alert_system = AnubisAlertSystem(db, None)

        # Program IDs for the platforms we're monitoring
        self.programs = {
            "pump_fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            "raydium_launchlab": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
            # Note: LetsBonk.fun uses the same Raydium LaunchLab program
        }
        
        # Pump.fun specific addresses
        self.pump_global = "4wTV1YmiEkRvAtNtsSGPtUrqRYQMe5SKy2uB4Jjaxnjf"
        self.pump_fee_recipient = "CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4xC9iM"
        
        # Track scanning status
        self.scan_status = {
            "running": False,
            "progress": 0,
            "total": 0,
            "last_checkpoint": None
        }

    async def start_scanning(self):
        """Main scanning loop - starts all scanners"""
        print("🚀 Starting wallet scanner...")
        print("👀 Monitoring Pump.fun and Raydium LaunchLab...")
        
        # Start the scanning tasks
        tasks = []
        
        # Add pump.fun historical scan
        tasks.append(self.scan_pump_historical())
        
        # Add real-time monitoring if you want
        # tasks.append(self.monitor_real_time())
        
        # Run all tasks
        if tasks:
            await asyncio.gather(*tasks)
        else:
            # Fallback - just run a simple scan loop
            while True:
                print(f"Scanning... {datetime.now()}")
                await asyncio.sleep(30)

    async def scan_pump_historical(self):
        """Monitor Pump.fun program directly via RPC"""
        print("📊 Monitoring Pump.fun program directly...")
        
        pump_program = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
        seen_signatures = set()  # Track what we've already processed
        
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    # Get recent signatures
                    response = await client.post(
                        self.helius_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getSignaturesForAddress",
                            "params": [pump_program, {"limit": 100}]
                        },
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        signatures = data.get('result', [])
                        
                        for sig_info in signatures:
                            signature = sig_info.get('signature')
                            
                            # Skip if we've seen this one
                            if signature in seen_signatures:
                                continue
                            seen_signatures.add(signature)
                            
                            # Fetch full transaction
                            tx_response = await client.post(
                                self.helius_url,
                                json={
                                    "jsonrpc": "2.0",
                                    "id": 1,
                                    "method": "getTransaction",
                                    "params": [
                                        signature,
                                        {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
                                    ]
                                },
                                timeout=30.0
                            )
                            
                            if tx_response.status_code == 200:
                                tx_data = tx_response.json()
                                result = tx_data.get('result')
                                
                                if result and result.get('meta', {}).get('err') is None:
                                    logs = result.get('meta', {}).get('logMessages', [])
                                    
                                    # Better launch detection
                                    is_launch = False
                                    for log in logs:
                                        if any(pattern in log for pattern in [
                                            "Program log: Instruction: Create",
                                            "create_pump",
                                            "InitializeMint",
                                            "init_pump_token"
                                        ]):
                                            is_launch = True
                                            break
                                    
                                    if is_launch:
                                        # Extract creator
                                        account_keys = result.get('transaction', {}).get('message', {}).get('accountKeys', [])
                                        creator = account_keys[0].get('pubkey') if account_keys else 'UNKNOWN'
                                        
                                        # Find mint in account keys
                                        mint = None
                                        for key in account_keys[1:4]:
                                            address = key.get('pubkey', '')
                                            if len(address) == 44 and address != pump_program:
                                                mint = address
                                                break
                                        
                                        if mint:
                                            print(f"   🚀 NEW TOKEN LAUNCH!")
                                            print(f"      Mint: {mint}")
                                            print(f"      Creator: {creator}")
                                            print(f"      Signature: {signature[:20]}...")
                                            
                                            # Store in database
                                            async with self.db.acquire() as conn:
                                                await conn.execute("""
                                                    INSERT INTO token_launches 
                                                    (mint_address, creator_wallet, platform, launch_time)
                                                    VALUES ($1, $2, $3, NOW())
                                                    ON CONFLICT (mint_address) DO NOTHING
                                                """, mint, creator, 'pump_fun')
                                            
                                            # ADD THIS PART - Check developer and send alerts
                                            await self.check_developer_profile(creator, {
                                                'mint': mint,
                                                'symbol': 'UNKNOWN',  # We don't have this yet from RPC
                                                'name': 'Unknown',     # We don't have this yet from RPC
                                                'market_cap': 0        # Would need separate API call
                                            })
                
                print(f"⏰ Checked {len(signatures)} transactions, waiting 30 seconds...")
                await asyncio.sleep(30)
                
            except Exception as e:
                print(f"❌ Error: {e}")
                await asyncio.sleep(30)
    
    async def get_token_creator(self, mint_address):
        """Get creator from the blockchain directly"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.helius_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [mint_address, {"limit": 1}]
                }
            )
            # Parse response to find creator...
            return response.json()

async def check_developer_profile(self, creator_wallet: str, token_info: dict):
    """Check developer profile and send appropriate alerts"""
    
    async with self.db.acquire() as conn:
        # Get developer profile
        profile = await conn.fetchrow("""
            SELECT * FROM anubis_wallet_profiles 
            WHERE wallet_address = $1
        """, creator_wallet)
        
        if not profile:
            return
        
        # Get their top successful tokens
        top_tokens = await conn.fetch("""
            SELECT token_symbol, token_name, peak_mcap
            FROM token_launches tl
            LEFT JOIN successful_tokens_archive sta ON tl.mint_address = sta.mint_address
            WHERE tl.creator_wallet = $1
            AND sta.peak_mcap > 100000
            ORDER BY sta.peak_mcap DESC
            LIMIT 5
        """, creator_wallet)
        
        # Send alerts based on tier
        if profile['developer_tier'] == 'ELITE':
            await self.send_elite_alert(profile, token_info, top_tokens)
        elif profile['risk_rating'] == 'EXTREME':
            await self.send_scam_alert(profile, token_info)

async def send_elite_alert(self, profile, token_info, top_tokens):
    """Send alert for elite developer"""
    message = f"🚨 ELITE DEVELOPER LAUNCH!\n"
    message += f"━━━━━━━━━━━━━━━━━━━━\n"
    message += f"New Token: ${token_info.get('symbol', 'UNKNOWN')}\n"
    message += f"Anubis Score: {profile['anubis_score']:.1f}\n\n"
    
    if top_tokens:
        message += "📜 PREVIOUS HITS:\n"
        for i, token in enumerate(top_tokens[:5], 1):
            message += f"{i}. ${token['token_symbol']} - ${token['peak_mcap']/1000000:.1f}M\n"
    
    message += f"\nSuccess Rate: {profile['success_rate']:.1f}%"
    
    # Send to Telegram
    channel_id = os.getenv('CRITICAL_ALERTS_CHANNEL')
    await self.send_telegram_message(channel_id, message)

async def send_telegram_message(self, channel_id, message):
    """Actually send message to Telegram"""
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not bot_token or not channel_id:
        print(f"Missing Telegram config - would send: {message}")
        return
    
    import httpx
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            'chat_id': channel_id,
            'text': message,
            'parse_mode': 'HTML'
        })
        if response.status_code == 200:
            print(f"✅ Alert sent to Telegram channel {channel_id}")

    async def fetch_token_metadata(self, mint_address: str) -> dict:
        """
        Fetch token metadata - tries multiple methods to ensure we get the data
        """
        metadata = {'name': 'Unknown', 'symbol': 'UNKNOWN', 'description': ''}
        
        try:
            async with httpx.AsyncClient() as client:
                # Method 1: Helius DAS API (most reliable for new tokens)
                try:
                    response = await client.post(
                        self.helius_url,
                        json={
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "getAsset",
                            "params": {"id": mint_address}
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        result = data.get('result', {})
                        content = result.get('content', {})
                        meta = content.get('metadata', {})
                        
                        if meta.get('symbol'):  # We got valid metadata
                            return {
                                'name': meta.get('name', 'Unknown'),
                                'symbol': meta.get('symbol', 'UNKNOWN'),
                                'description': meta.get('description', ''),
                                'image': content.get('links', {}).get('image', '')
                            }
                except:
                    pass
                
                # Method 2: Try Pump.fun API directly (if it's a pump token)
                try:
                    response = await client.get(
                        f"https://frontend-api.pump.fun/coins/{mint_address}",
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Accept': 'application/json'
                        },
                        timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('symbol'):
                            return {
                                'name': data.get('name', 'Unknown'),
                                'symbol': data.get('symbol', 'UNKNOWN'),
                                'description': data.get('description', ''),
                                'market_cap': data.get('usd_market_cap', 0)
                            }
                except:
                    pass
                
                # Method 3: Get from Metaplex metadata account
                try:
                    # Calculate metadata PDA
                    from solders.pubkey import Pubkey
                    from solders.system_program import ID as SYSTEM_PROGRAM_ID
                    
                    METADATA_PROGRAM_ID = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
                    seeds = [
                        b"metadata",
                        bytes.fromhex(METADATA_PROGRAM_ID.replace("0x", "")),
                        bytes.fromhex(mint_address.replace("0x", ""))
                    ]
                    
                    # This would need the actual PDA derivation
                    # For now, we'll mark this as a TODO
                    pass
                except:
                    pass
                
                # Method 4: Wait a bit and retry (new tokens need time to propagate)
                await asyncio.sleep(2)
                
                # Retry Method 1 after delay
                response = await client.post(
                    self.helius_url,
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getAsset",
                        "params": {"id": mint_address}
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get('result', {})
                    content = result.get('content', {})
                    meta = content.get('metadata', {})
                    
                    if meta.get('symbol'):
                        metadata = {
                            'name': meta.get('name', 'Unknown'),
                            'symbol': meta.get('symbol', 'UNKNOWN'),
                            'description': meta.get('description', '')
                        }
                        
        except Exception as e:
            print(f"Error fetching metadata for {mint_address}: {e}")
        
        # If we still don't have metadata, mark it for retry
        if metadata['symbol'] == 'UNKNOWN':
            print(f"   ⚠️ Could not fetch metadata for {mint_address} - will retry later")
            # Store in a retry queue
            async with self.db.acquire() as conn:
                await conn.execute("""
                    INSERT INTO metadata_retry_queue (mint_address, retry_count, next_retry)
                    VALUES ($1, 0, NOW() + INTERVAL '1 minute')
                    ON CONFLICT (mint_address) DO NOTHING
                """, mint_address)
        
        return metadata

    async def retry_metadata_fetches(self):
        """Background task to retry failed metadata fetches"""
        while True:
            try:
                async with self.db.acquire() as conn:
                    # Get tokens that need metadata retry
                    tokens = await conn.fetch("""
                        SELECT mint_address FROM metadata_retry_queue 
                        WHERE next_retry < NOW() AND retry_count < 5
                        LIMIT 10
                    """)
                    
                    for token in tokens:
                        metadata = await self.fetch_token_metadata(token['mint_address'])
                        
                        if metadata['symbol'] != 'UNKNOWN':
                            # Success! Update the token_launches table
                            await conn.execute("""
                                UPDATE token_launches 
                                SET token_name = $1, token_symbol = $2
                                WHERE mint_address = $3
                            """, metadata['name'], metadata['symbol'], token['mint_address'])
                            
                            # Remove from retry queue
                            await conn.execute("""
                                DELETE FROM metadata_retry_queue 
                                WHERE mint_address = $1
                            """, token['mint_address'])
                            
                            print(f"   ✅ Metadata updated: ${metadata['symbol']} - {metadata['name']}")
                        else:
                            # Still failed, increment retry count
                            await conn.execute("""
                                UPDATE metadata_retry_queue 
                                SET retry_count = retry_count + 1,
                                    next_retry = NOW() + INTERVAL '5 minutes'
                                WHERE mint_address = $1
                            """, token['mint_address'])
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                print(f"Error in metadata retry: {e}")
                await asyncio.sleep(60)


    # ============= HISTORICAL SCANNING =============
    
    async def run_historical_scan(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Scan historical data for both platforms
        This is called once to populate the database with past data
        """
        self.scan_status["running"] = True
        self.scan_status["progress"] = 0
        
        logger.info(f"Starting historical scan from {start_date} to {end_date}")
        
        all_results = {}
        
        try:
            for platform_name, program_id in self.programs.items():
                logger.info(f"Scanning {platform_name}...")
                
                platform_results = await self._scan_platform_history(
                    program_id, 
                    platform_name,
                    start_date, 
                    end_date
                )
                
                all_results[platform_name] = platform_results
                
                # Store results as we go
                await self._store_historical_results(platform_name, platform_results)
                
                # Update developer profiles
                await self._update_developer_profiles(platform_results)
                
        except Exception as e:
            logger.error(f"Historical scan error: {e}")
            raise
        finally:
            self.scan_status["running"] = False
            
        return all_results

    async def _scan_platform_history(self, program_id: str, platform: str, 
                                    start_date: datetime, end_date: datetime) -> List[Dict]:
        """Scan a specific platform's history using Helius RPC"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_launches = []
            before_signature = None
            
            while True:
                # Get signatures for the program
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getSignaturesForAddress",
                    "params": [
                        program_id,
                        {
                            "limit": 1000,
                            "before": before_signature,
                            "commitment": "confirmed"
                        }
                    ]
                }
                
                try:
                    response = await client.post(self.helius_url, json=payload)
                    data = response.json()
                    
                    if "result" not in data or not data["result"]:
                        break
                    
                    signatures = data["result"]
                    
                    for sig_info in signatures:
                        block_time = sig_info.get("blockTime", 0)
                        if block_time == 0:
                            continue
                        
                        sig_date = datetime.fromtimestamp(block_time)
                        
                        # Check date range
                        if sig_date < start_date:
                            return all_launches  # We've gone too far back
                        
                        if sig_date > end_date:
                            continue
                        
                        # Get and parse the transaction
                        tx_data = await self._get_transaction(client, sig_info["signature"])
                        
                        if tx_data:
                            launch_info = await self._parse_launch_transaction(
                                tx_data, 
                                platform, 
                                sig_date
                            )
                            
                            if launch_info:
                                all_launches.append(launch_info)
                                
                                # Update progress
                                self.scan_status["progress"] += 1
                                
                                if len(all_launches) % 100 == 0:
                                    logger.info(f"{platform}: Found {len(all_launches)} launches")
                    
                    # Pagination
                    before_signature = signatures[-1]["signature"]
                    
                    # Rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"Error scanning {platform}: {e}")
                    await asyncio.sleep(1)  # Back off on error
                    
            return all_launches

    async def _get_transaction(self, client: httpx.AsyncClient, signature: str) -> Optional[Dict]:
        """Fetch full transaction data from Helius"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0
                }
            ]
        }
        
        try:
            response = await client.post(self.helius_url, json=payload)
            data = response.json()
            return data.get("result")
        except Exception as e:
            logger.error(f"Error getting transaction {signature}: {e}")
            return None

    async def _parse_launch_transaction(self, tx_data: Dict, platform: str, 
                                       timestamp: datetime) -> Optional[Dict]:
        """Parse transaction to extract token launch information"""
        try:
            if not tx_data or "meta" not in tx_data:
                return None
            
            # Check if this is actually a token launch
            if not self._is_token_launch(tx_data, platform):
                return None
            
            launch_info = {
                "signature": tx_data["transaction"]["signatures"][0],
                "platform": platform,
                "launch_time": timestamp,
                "creator_wallet": None,
                "mint_address": None,
                "token_name": None,
                "token_symbol": None,
                "initial_liquidity_sol": 0,
                "metadata": {}
            }
            
            # Get creator (fee payer is usually the creator)
            account_keys = tx_data["transaction"]["message"]["accountKeys"]
            if account_keys:
                launch_info["creator_wallet"] = account_keys[0]["pubkey"]
            
            # Extract mint address and token info
            inner_instructions = tx_data["meta"].get("innerInstructions", [])
            for inner in inner_instructions:
                for instruction in inner.get("instructions", []):
                    if instruction.get("program") == "spl-token":
                        parsed = instruction.get("parsed", {})
                        if parsed.get("type") == "initializeMint":
                            launch_info["mint_address"] = parsed["info"]["mint"]
            
            # Calculate SOL spent (initial liquidity)
            pre_balances = tx_data["meta"]["preBalances"]
            post_balances = tx_data["meta"]["postBalances"]
            
            if pre_balances and post_balances and len(pre_balances) > 0:
                sol_spent = (pre_balances[0] - post_balances[0]) / 1e9
                launch_info["initial_liquidity_sol"] = max(0, sol_spent)
            
            return launch_info
            
        except Exception as e:
            logger.error(f"Error parsing launch transaction: {e}")
            return None

    def _is_token_launch(self, tx_data: Dict, platform: str) -> bool:
        """Determine if a transaction is a token launch"""
        # Check log messages for launch indicators
        logs = tx_data["meta"].get("logMessages", [])
        
        if platform == "pump_fun":
            for log in logs:
                if "Program log: Instruction: Create" in log:
                    return True
                if "create" in log.lower() and "token" in log.lower():
                    return True
                    
        elif platform == "raydium_launchlab":
            for log in logs:
                if "initialize" in log.lower():
                    return True
        
        # Check for mint initialization
        inner_instructions = tx_data["meta"].get("innerInstructions", [])
        for inner in inner_instructions:
            for instruction in inner.get("instructions", []):
                if instruction.get("program") == "spl-token":
                    if instruction.get("parsed", {}).get("type") == "initializeMint":
                        return True
        
        return False

    async def _store_historical_results(self, platform: str, results: List[Dict]):
        """Store historical scan results in the database"""
        if not results:
            return
        
        async with self.db.acquire() as conn:
            for launch in results:
                try:
                    # Store in token_launches table
                    await conn.execute("""
                        INSERT INTO token_launches 
                        (mint_address, creator_wallet, platform, launch_time, 
                         initial_liquidity_sol, signature, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (mint_address) DO UPDATE SET
                            platform = EXCLUDED.platform,
                            launch_time = EXCLUDED.launch_time
                    """,
                        launch.get("mint_address"),
                        launch.get("creator_wallet"),
                        platform,
                        launch.get("launch_time"),
                        launch.get("initial_liquidity_sol", 0),
                        launch.get("signature"),
                        json.dumps(launch.get("metadata", {}))
                    )
                    
                    # Check if this token was successful (>$100K market cap)
                    market_cap = await self._get_token_market_cap(launch.get("mint_address"))
                    
                    if market_cap and market_cap > 100000:
                        await conn.execute("""
                            INSERT INTO successful_tokens_archive
                            (mint_address, creator_wallet, platform, launch_date, peak_mcap)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (mint_address) DO UPDATE SET
                                peak_mcap = GREATEST(successful_tokens_archive.peak_mcap, $5)
                        """,
                            launch.get("mint_address"),
                            launch.get("creator_wallet"),
                            platform,
                            launch.get("launch_time"),
                            market_cap
                        )

                    if launch.get("creator_wallet") and self.scoring_engine:
                        try:
                            await self.scoring_engine.calculate_anubis_score(
                                launch.get("creator_wallet")
                            )
                        except Exception as e:
                            logger.error(f"Error calculating Anubis score: {e}")
                
                except Exception as e:
                    print(f"Error in token processing: {e}")
                    continue

    async def _update_developer_profiles(self, launches: List[Dict]):
        """Update developer wallet profiles based on launch history"""
        # Group launches by creator
        creators = {}
        for launch in launches:
            creator = launch.get("creator_wallet")
            if creator:
                if creator not in creators:
                    creators[creator] = []
                creators[creator].append(launch)
        
        async with self.db.acquire() as conn:
            for wallet, wallet_launches in creators.items():
                try:
                    # Calculate metrics
                    total_launches = len(wallet_launches)
                    avg_liquidity = sum(l.get("initial_liquidity_sol", 0) 
                                      for l in wallet_launches) / total_launches
                    
                    # Update or create profile
                    await conn.execute("""
                        INSERT INTO historical_wallet_profiles
                        (wallet_address, total_launches, avg_seed_amount, 
                         first_seen, last_active)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (wallet_address) DO UPDATE SET
                            total_launches = historical_wallet_profiles.total_launches + $2,
                            avg_seed_amount = $3,
                            last_active = $5
                    """,
                        wallet,
                        total_launches,
                        avg_liquidity,
                        min(l["launch_time"] for l in wallet_launches),
                        max(l["launch_time"] for l in wallet_launches)
                    )
                    
                except Exception as e:
                    logger.error(f"Error updating profile for {wallet}: {e}")

    async def _get_token_market_cap(self, mint_address: str) -> Optional[float]:
        """Get current market cap for a token using Jupiter API"""
        if not mint_address:
            return None
            
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Use Jupiter price API
                url = f"https://price.jup.ag/v4/price?ids={mint_address}"
                response = await client.get(url)
                
                if response.status_code == 200:
                    data = response.json()
                    if mint_address in data.get("data", {}):
                        return data["data"][mint_address].get("marketCap", 0)
                        
        except Exception as e:
            logger.debug(f"Could not get market cap for {mint_address}: {e}")
            
        return None

    # ============= REAL-TIME MONITORING =============
    
    async def start_realtime_monitoring(self):
        """Start real-time monitoring of both platforms"""
        logger.info("Starting real-time monitoring for Pump.fun and LaunchLab...")
        
        # Run both monitors concurrently
        await asyncio.gather(
            self._monitor_pump_fun(),
            self._monitor_launchlab(),
            return_exceptions=True
        )

    async def _monitor_pump_fun(self):
        """Monitor Pump.fun launches in real-time via WebSocket"""
        while True:
            try:
                async with connect(self.helius_ws_url) as websocket:
                    # Subscribe to Pump.fun program logs
                    await websocket.send(json.dumps({
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [self.programs["pump_fun"]]},
                            {"commitment": "confirmed"}
                        ]
                    }))
                    
                    logger.info("Connected to Pump.fun WebSocket monitor")
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            
                            if "params" in data and "result" in data["params"]:
                                await self._process_realtime_launch(
                                    data["params"]["result"],
                                    "pump_fun"
                                )
                                
                        except Exception as e:
                            logger.error(f"Error processing Pump.fun message: {e}")
                            
            except Exception as e:
                logger.error(f"Pump.fun WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect after 5 seconds

    async def _monitor_launchlab(self):
        """Monitor Raydium LaunchLab (includes LetsBonk.fun) in real-time"""
        while True:
            try:
                async with connect(self.helius_ws_url) as websocket:
                    # Subscribe to LaunchLab program logs
                    await websocket.send(json.dumps({
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "logsSubscribe",
                        "params": [
                            {"mentions": [self.programs["raydium_launchlab"]]},
                            {"commitment": "confirmed"}
                        ]
                    }))
                    
                    logger.info("Connected to LaunchLab WebSocket monitor")
                    
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            
                            if "params" in data and "result" in data["params"]:
                                await self._process_realtime_launch(
                                    data["params"]["result"],
                                    "raydium_launchlab"
                                )
                                
                        except Exception as e:
                            logger.error(f"Error processing LaunchLab message: {e}")
                            
            except Exception as e:
                logger.error(f"LaunchLab WebSocket error: {e}")
                await asyncio.sleep(5)  # Reconnect after 5 seconds

    async def _process_realtime_launch(self, log_result: Dict, platform: str):
        """Process a real-time token launch detection"""
        try:
            signature = log_result.get("signature")
            logs = log_result.get("logs", [])
            
            # Quick check if this might be a launch
            is_launch = False
            for log in logs:
                if any(keyword in log.lower() for keyword in ["create", "initialize", "mint"]):
                    is_launch = True
                    break
            
            if not is_launch:
                return
            
            # Get full transaction details
            async with httpx.AsyncClient() as client:
                tx_data = await self._get_transaction(client, signature)
                
                if tx_data:
                    launch_info = await self._parse_launch_transaction(
                        tx_data, 
                        platform,
                        datetime.now()
                    )
                    
                    if launch_info:
                        logger.info(f"🚀 New {platform} launch detected: {launch_info['mint_address']}")
                        
                        # Store in database
                        await self._store_realtime_launch(launch_info)
                        
                        # Check developer history for alerts
                        await self.alert_system.process_new_launch(
                            wallet=launch_info['creator_wallet'],
                            token=launch_info['mint_address'],
                            platform=platform
                        )
                        
        except Exception as e:
            logger.error(f"Error processing realtime launch: {e}")

    async def _store_realtime_launch(self, launch_info: Dict):
        """Store real-time launch in database and update rolling window"""
        async with self.db.acquire() as conn:
            # Store in main table
            await conn.execute("""
                INSERT INTO token_launches 
                (mint_address, creator_wallet, platform, launch_time, 
                 initial_liquidity_sol, signature, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (mint_address) DO NOTHING
            """,
                launch_info.get("mint_address"),
                launch_info.get("creator_wallet"),
                launch_info.get("platform"),
                launch_info.get("launch_time"),
                launch_info.get("initial_liquidity_sol", 0),
                launch_info.get("signature"),
                json.dumps(launch_info.get("metadata", {}))
            )
            
            # Add to active monitoring
            await conn.execute("""
                INSERT INTO active_monitoring
                (wallet_address, token_address, platform, detected_at)
                VALUES ($1, $2, $3, NOW())
            """,
                launch_info.get("creator_wallet"),
                launch_info.get("mint_address"),
                launch_info.get("platform")
            )

    async def _check_developer_alerts(self, launch_info: Dict):
        """Check if this developer triggers any alert conditions"""
        creator = launch_info.get("creator_wallet")
        if not creator:
            return
        
        async with self.db.acquire() as conn:
            # Get developer profile
            profile = await conn.fetchrow("""
                SELECT * FROM historical_wallet_profiles
                WHERE wallet_address = $1
            """, creator)
            
            if profile:
                # Check if this is a known rugger
                if profile.get("total_rugs", 0) > 5:
                    logger.warning(f"⚠️ KNOWN RUGGER ALERT: {creator}")
                    # Here you would trigger Telegram alerts
                    
                # Check if this developer has successful history
                if profile.get("successful_launches", 0) > 0:
                    success_rate = profile["successful_launches"] / profile["total_launches"]
                    if success_rate > 0.3:
                        logger.info(f"✅ Successful developer detected: {creator} ({success_rate:.1%} success rate)")
                        # Trigger positive alert

# Create alias for backward compatibility
HistoricalScanner = WalletScanner


# ============= STANDALONE FUNCTIONS =============
# These are module-level functions, not class methods

async def connect_database():
    """Connect to DigitalOcean Managed PostgreSQL"""
    
    # DigitalOcean connection format
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    if not DATABASE_URL:
        # Get these from your DigitalOcean database dashboard
        DB_HOST = os.getenv('DB_HOST')
        DB_PORT = os.getenv('DB_PORT', '25060')
        DB_NAME = os.getenv('DB_NAME', 'defaultdb')
        DB_USER = os.getenv('DB_USER', 'doadmin')
        DB_PASSWORD = os.getenv('DB_PASSWORD')
        
        DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?sslmode=require"
    
    print(f"Connecting to DigitalOcean database...")
    
    # Connect with SSL required
    return await asyncpg.create_pool(
        DATABASE_URL,
        ssl='require',
        min_size=1,
        max_size=10
    )

async def main():
    """Main entry point for the scanner"""
    print("Main function called...")
    try:
        db = await connect_database()
        print(f"✅ Database connected!")
        
        # Create and start the scanner
        scanner = WalletScanner(db)
        await scanner.start_scanning()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

# Entry point
if __name__ == "__main__":
    print("Running scanner...")
    asyncio.run(main())