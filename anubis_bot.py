"""
Anubis Bot - Complete Implementation with Error Handling
"""

import os
import sys
import logging
import asyncio
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from modules.historical_scanner import HistoricalScanner
from modules.wallet_scanner import WalletScanner
from utils.reportMissingImports2 import check_imports

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from loguru import logger

# Import local modules
from database import Database
from pump_monitor import PumpFunMonitor

# Load environment variables
load_dotenv()

# Remove default logger and configure loguru
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG" if os.getenv('BOT_ENV') == 'development' else "INFO"
)
logger.add(
    "logs/anubis_{time}.log",
    rotation="1 day",
    retention="7 days",
    format="{time} | {level} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)

# Bot configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL')
ENVIRONMENT = os.getenv('BOT_ENV', 'development')
ADMIN_TELEGRAM_ID = os.getenv('ADMIN_TELEGRAM_ID')
ADMIN_IDS = [int(ADMIN_TELEGRAM_ID)] if ADMIN_TELEGRAM_ID else []

# Anubis bot version
ANUBIS_VERSION = "2.0.0"

# Emoji constants
EMOJI = {
    'rocket': '🚀',
    'check': '✅',
    'cross': '❌',
    'warning': '⚠️',
    'money': '💰',
    'chart': '📈',
    'fire': '🔥',
    'skull': '💀',
    'gem': '💎',
    'eye': '👁',
    'siren': '🚨',
    'bell': '🔔',
    'mute': '🔕'
}

"""
Historical Multi-Platform Scanner
One-time historical data collection
"""

class HistoricalScanner:
    def __init__(self, db):
        self.db = db
        self.helius_key = os.getenv('HELIUS_API_KEY')
        self.helius_url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_key}"
        
        # All platforms to scan historically
        self.platforms = {
            "pump_fun": "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",
            "raydium_launchlab": "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj",
            "moonshot": "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG",
            "raydium_amm": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
        }
        
    async def run_historical_scan(self, start_date: datetime, end_date: datetime):
        """
        Sequential scan of all platforms for historical data
        This runs ONCE to populate the database
        """
        
        all_results = {}
        
        for platform_name, program_id in self.platforms.items():
            logger.info(f"Scanning {platform_name} from {start_date} to {end_date}")
            
            # Scan this platform's entire history
            launches = await self.scan_platform_history(
                program_id, 
                platform_name,
                start_date, 
                end_date
            )
            
            all_results[platform_name] = launches
            
            # Process and store successful launches
            await self.process_platform_results(platform_name, launches)
            
            # Be nice to RPC
            await asyncio.sleep(1)
        
        return all_results
    
    async def scan_platform_history(self, program_id: str, platform: str, 
                                   start_date: datetime, end_date: datetime):
        """
        Get ALL historical transactions for a single platform
        """
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_launches = []
            before_signature = None
            
            while True:
                # Get batch of signatures
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
                
                response = await client.post(self.helius_url, json=payload)
                data = response.json()
                
                if "result" not in data or not data["result"]:
                    break
                
                signatures = data["result"]
                
                # Process signatures in this batch
                for sig_info in signatures:
                    block_time = sig_info.get("blockTime", 0)
                    if block_time == 0:
                        continue
                    
                    sig_date = datetime.fromtimestamp(block_time)
                    
                    # Check date range
                    if sig_date < start_date:
                        return all_launches  # We've gone too far back
                    
                    if sig_date > end_date:
                        continue  # Skip future dates
                    
                    # Get and parse transaction
                    tx_data = await self.get_transaction(client, sig_info["signature"])
                    
                    if platform == "pump_fun":
                        launch_info = self.parse_pump_fun_launch(tx_data)
                    elif platform == "raydium_launchlab":
                        launch_info = self.parse_launchlab_launch(tx_data)
                    else:
                        launch_info = self.parse_generic_launch(tx_data)
                    
                    if launch_info:
                        launch_info["platform"] = platform
                        launch_info["launch_time"] = sig_date
                        all_launches.append(launch_info)
                
                # Pagination
                before_signature = signatures[-1]["signature"]
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
                # Progress update
                if len(all_launches) % 1000 == 0:
                    logger.info(f"{platform}: Found {len(all_launches)} launches so far...")
            
        return all_launches
    
    async def process_platform_results(self, platform: str, launches: List[Dict]):
        """
        Store successful launches and update developer profiles
        """
        
        successful_count = 0
        
        for launch in launches:
            if not launch.get("mint_address"):
                continue
            
            # Get token performance (market cap)
            performance = await self.get_token_performance(launch["mint_address"])
            
            # Only store if successful (>$100K peak)
            if performance.get("peak_market_cap", 0) > 100_000:
                successful_count += 1
                
                # Store in archive
                await self.store_successful_token(launch, performance)
                
                # Update developer profile
                await self.update_developer_profile(
                    launch["creator_wallet"], 
                    platform,
                    launch, 
                    performance
                )
        
        logger.info(f"{platform}: {successful_count}/{len(launches)} successful (>{100}K)")



class AnubisBot:
    """Main Anubis Bot class with database integration and error handling"""
    
    def __init__(self):
        self.token = BOT_TOKEN
        self.db = None
        self.pump_monitor = None
        self.application = None
        self.monitor_task = None
        self.start_time = datetime.now()
        
        # Verify token exists
        if not self.token:
            logger.critical("TELEGRAM_BOT_TOKEN not found in environment variables!")
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
    
    async def startup_diagnostics(self) -> Dict[str, Any]:
        """Run startup diagnostics"""
        checks = {
            'telegram_token': False,
            'database': False,
            'solana_rpc': False
        }
        errors = []
        
        # Check Telegram token
        if self.token:
            checks['telegram_token'] = True
            logger.info("✅ Telegram token verified")
        else:
            errors.append("❌ TELEGRAM_BOT_TOKEN not set")
        
        if self.db:
            from modules.anubis_scoring import AnubisScoringEngine, AnubisAlertSystem
            self.scoring_engine = AnubisScoringEngine(self.db.pool)
            self.alert_system = AnubisAlertSystem(self.db.pool, application.bot)

        # Check database connection
        try:
            if DATABASE_URL:
                self.db = Database(DATABASE_URL)
                await self.db.connect()
                checks['database'] = True
                logger.info("✅ Database connection verified")
            else:
                errors.append("❌ DATABASE_URL not set")
        except Exception as e:
            errors.append(f"❌ Database connection failed: {e}")
            logger.error(f"Database check failed: {e}")
        
        # Check Solana RPC
        if SOLANA_RPC_URL:
            checks['solana_rpc'] = True
            logger.info("✅ Solana RPC URL configured")
        else:
            logger.warning("⚠️ SOLANA_RPC_URL not set - monitoring disabled")
        
        # Log results
        logger.info("="*50)
        logger.info("STARTUP DIAGNOSTICS COMPLETE")
        logger.info(f"✅ Passed: {sum(checks.values())}/{len(checks)}")
        for service, status in checks.items():
            logger.info(f"  {service}: {'✅' if status else '❌'}")
        if errors:
            logger.error("STARTUP ERRORS:")
            for error in errors:
                logger.error(f"  {error}")
        logger.info("="*50)
        
        return {'checks': checks, 'errors': errors}
    
    async def post_init(self, application: Application) -> None:
        """Initialize after application is created"""
        try:
            # Run diagnostics
            diagnostics = await self.startup_diagnostics()
            
            # Initialize database if not already connected
            if not self.db and DATABASE_URL:
                self.db = Database(DATABASE_URL)
                await self.db.connect()
            
            # Initialize Pump.fun monitor if RPC available
            if SOLANA_RPC_URL and self.db:
                try:
                    self.pump_monitor = PumpFunMonitor(SOLANA_RPC_URL, self.db)
                    self.monitor_task = asyncio.create_task(self.monitor_with_recovery())
                    logger.info("✅ Pump.fun monitor started")
                except Exception as e:
                    logger.error(f"Failed to start Pump.fun monitor: {e}")
                    # Bot can still run without monitor
            
            logger.info(f"✅ Anubis Bot v{ANUBIS_VERSION} initialization complete")
            
        except Exception as e:
            logger.critical(f"INITIALIZATION FAILED: {e}")
            # Continue running with limited functionality
    
    async def post_shutdown(self, application: Application) -> None:
        """Cleanup on shutdown"""
        logger.info("Shutting down Anubis Bot...")
        
        if self.monitor_task:
            self.monitor_task.cancel()
        
        if self.pump_monitor:
            await self.pump_monitor.stop_monitoring()
        
        if self.db:
            await self.db.disconnect()
        
        logger.info("✅ Shutdown complete")
    
    async def monitor_with_recovery(self):
        """Monitor with automatic recovery on failure"""
        while True:
            try:
                if self.pump_monitor:
                    await self.pump_monitor.start_monitoring()
            except Exception as e:
                logger.error(f"Monitor crashed: {e}. Restarting in 30 seconds...")
                await asyncio.sleep(30)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user = update.effective_user
        
        try:
            # Save user to database if available
            if self.db:
                await self.db.upsert_user(
                    user.id,
                    username=user.username,
                    first_name=user.first_name
                )
            
            welcome_message = f"""
{EMOJI['rocket']} **Welcome to Anubis Bot** {EMOJI['eye']}

Track Solana developer wallets and get real-time alerts!

**Available Commands:**
/track `<wallet>` - Track a developer wallet
/list - Show your tracked wallets
/stats `<wallet>` - Get developer statistics
/recent - Show recent launches
/top - Top performing developers
/alerts - Configure notifications
/help - Show detailed help

**Quick Start:**
Send me a Solana wallet address to start tracking!

Version: {ANUBIS_VERSION}
Status: {'🟢 Online' if self.db else '🟡 Limited Mode'}
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("📊 Recent Launches", callback_data="recent"),
                    InlineKeyboardButton("🔥 Top Devs", callback_data="top_devs")
                ],
                [
                    InlineKeyboardButton("📖 Guide", callback_data="guide"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
            logger.info(f"User {user.id} (@{user.username}) started the bot")
            
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await self.send_error_message(update, "startup")
    
    async def track_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Track a developer wallet"""
        user = update.effective_user
        
        try:
            if not context.args:
                await update.message.reply_text(
                    f"{EMOJI['warning']} Please provide a wallet address:\n"
                    "`/track <wallet_address>`",
                    parse_mode='Markdown'
                )
                return
            
            wallet_address = context.args[0]
            
            # Basic Solana address validation
            if not (32 <= len(wallet_address) <= 44):
                await update.message.reply_text(
                    f"{EMOJI['cross']} Invalid Solana wallet format!\n"
                    "Addresses should be 32-44 characters long.",
                    parse_mode='Markdown'
                )
                return
            
            if self.db:
                # Track the wallet
                success = await self.db.track_wallet(user.id, wallet_address)
                
                if success:
                    # Get developer stats if available
                    developer = await self.db.get_developer(wallet_address)
                    
                    if developer and developer.get('total_launches', 0) > 0:
                        msg = f"""
{EMOJI['check']} **Tracking Started**

Address: `{wallet_address[:8]}...{wallet_address[-8:]}`

**Developer Stats:**
- Total Launches: {developer['total_launches']}
- Success Rate: {developer.get('success_rate', 0):.1f}%
- Last Active: {developer.get('last_active', 'Unknown')}

You'll receive alerts for new launches!
                        """
                    else:
                        msg = f"""
{EMOJI['check']} **Tracking Started**

Address: `{wallet_address[:8]}...{wallet_address[-8:]}`

No historical data yet. I'll alert you when this wallet launches tokens.
                        """
                    
                    await update.message.reply_text(msg, parse_mode='Markdown')
                else:
                    await update.message.reply_text(
                        f"{EMOJI['warning']} Already tracking this wallet or database error.",
                        parse_mode='Markdown'
                    )
            else:
                # Database not available - limited mode
                await update.message.reply_text(
                    f"{EMOJI['warning']} Bot is in limited mode. Database unavailable.\n"
                    f"Wallet noted: `{wallet_address[:8]}...{wallet_address[-8:]}`",
                    parse_mode='Markdown'
                )
            
            logger.info(f"User {user.id} tracking wallet: {wallet_address}")
            
        except Exception as e:
            logger.error(f"Error in track_command: {e}")
            await self.send_error_message(update, "tracking")
    
async def admin_scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: Run historical wallet scan"""
    user_id = update.effective_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("Unauthorized.")
        return
    
    from modules.wallet_scanner import WalletScanner
    scanner = WalletScanner(self.db, context.bot)
    
    # Parse command: /admin_scan [historical|active|status]
    if not context.args:
        msg = """Admin Scanner Commands:
/admin_scan historical - Run 3-year scan (once per year)
/admin_scan active - Update last 90 days
/admin_scan status - Check scan progress"""
        await update.message.reply_text(msg)
        return
    
    command = context.args[0]
    
    if command == "historical":
        await update.message.reply_text("🔍 Starting historical scan... This will take several hours.")
        asyncio.create_task(scanner.run_historical_scan(update.message.chat_id, context.bot))
        
    elif command == "active":
        await update.message.reply_text("📊 Updating active wallets (last 90 days)...")
        asyncio.create_task(scanner.update_active_wallets(update.message.chat_id, context.bot))
        
    elif command == "status":
        status = await scanner.get_scan_status()
        await update.message.reply_text(f"Scan Status:\n{status}")

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List tracked wallets"""
        user_id = update.effective_user.id
        
        try:
            if not self.db:
                await update.message.reply_text(
                    f"{EMOJI['warning']} Database unavailable. Cannot retrieve tracked wallets.",
                    parse_mode='Markdown'
                )
                return
            
            wallets = await self.db.get_tracked_wallets(user_id)
            
            if not wallets:
                await update.message.reply_text(
                    f"You're not tracking any wallets yet.\n"
                    f"Use `/track <wallet>` to start!",
                    parse_mode='Markdown'
                )
                return
            
            msg = f"{EMOJI['eye']} **Your Tracked Wallets**\n\n"
            
            for wallet in wallets[:10]:  # Limit to 10 for message length
                addr = wallet['wallet_address']
                alias = wallet.get('alias') or f"{addr[:8]}...{addr[-8:]}"
                
                launches = wallet.get('total_launches', 0)
                success_rate = wallet.get('success_rate', 0)
                
                if launches > 0:
                    msg += f"• `{alias}`\n  Launches: {launches} | Success: {success_rate:.1f}%\n\n"
                else:
                    msg += f"• `{alias}`\n  No launch data yet\n\n"
            
            if len(wallets) > 10:
                msg += f"\n_...and {len(wallets) - 10} more wallets_"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in list_command: {e}")
            await self.send_error_message(update, "listing wallets")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show developer statistics"""
        try:
            if not context.args:
                await update.message.reply_text(
                    f"{EMOJI['warning']} Please provide a wallet address:\n"
                    "`/stats <wallet_address>`",
                    parse_mode='Markdown'
                )
                return
            
            wallet_address = context.args[0]
            
            if not self.db:
                await update.message.reply_text(
                    f"{EMOJI['warning']} Database unavailable. Cannot retrieve stats.",
                    parse_mode='Markdown'
                )
                return
            
            # Get developer data
            developer = await self.db.get_developer(wallet_address)
            
            if not developer or developer.get('total_launches', 0) == 0:
                await update.message.reply_text(
                    f"No data available for wallet:\n`{wallet_address[:8]}...{wallet_address[-8:]}`",
                    parse_mode='Markdown'
                )
                return
            
            # Get pattern analysis if monitor available
            patterns = {}
            if self.pump_monitor:
                patterns = await self.pump_monitor.analyze_developer_patterns(wallet_address)
            
            msg = f"""
{EMOJI['chart']} **Developer Statistics**

Wallet: `{wallet_address[:8]}...{wallet_address[-8:]}`

**Launch History:**
- Total Launches: {developer['total_launches']}
- Successful: {developer.get('successful_launches', 0)}
- Success Rate: {developer.get('success_rate', 0):.1f}%

**Financial Performance:**
- Total Earnings: ${developer.get('total_earnings', 0):,.0f}
- Average Earnings: ${developer.get('average_earnings', 0):,.0f}
- Highest ATH: ${developer.get('highest_ath', 0):,.0f}
            """
            
            if patterns.get('preferred_hour') is not None:
                msg += f"""

**Patterns Detected:**
- Preferred Hour: {patterns['preferred_hour']:02d}:00 UTC
- Preferred Day: {patterns.get('preferred_day', 'Unknown')}
- Avg Liquidity: {patterns.get('avg_liquidity', 0):.2f} SOL
                """
            
            if developer.get('last_launch_time'):
                last_launch = developer['last_launch_time']
                if isinstance(last_launch, str):
                    msg += f"\n\nLast Launch: {last_launch}"
                else:
                    msg += f"\n\nLast Launch: {last_launch.strftime('%Y-%m-%d %H:%M')} UTC"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in stats_command: {e}")
            await self.send_error_message(update, "retrieving stats")
    
    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show recent launches"""
        try:
            if not self.db:
                await update.message.reply_text(
                    f"{EMOJI['warning']} Database unavailable. Cannot retrieve recent launches.",
                    parse_mode='Markdown'
                )
                return
            
            launches = await self.db.get_recent_launches(hours=24)
            
            if not launches:
                await update.message.reply_text(
                    "No launches detected in the last 24 hours.",
                    parse_mode='Markdown'
                )
                return
            
            msg = f"{EMOJI['rocket']} **Recent Launches (24h)**\n\n"
            
            for launch in launches[:10]:
                time_str = launch['launch_time']
                if hasattr(time_str, 'strftime'):
                    time_str = time_str.strftime('%H:%M')
                
                creator = launch['creator_wallet'][:8] + "..."
                
                msg += f"• {time_str} - "
                if launch.get('token_symbol'):
                    msg += f"${launch['token_symbol']} "
                msg += f"by {creator}\n"
                
                if launch.get('initial_liquidity_sol'):
                    msg += f"  Liquidity: {launch['initial_liquidity_sol']:.2f} SOL\n"
                
                msg += "\n"
            
            await update.message.reply_text(msg, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in recent_command: {e}")
            await self.send_error_message(update, "retrieving recent launches")
    
    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show top performing developers"""
        # TODO: Implement with real data from database
        msg = f"""
{EMOJI['fire']} **Top Performing Developers**

Feature coming soon! This will show:
- Highest success rate developers
- Most profitable launches
- Trending developers

Stay tuned!
        """
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Configure alert settings"""
        keyboard = [
            [
                InlineKeyboardButton("🔔 Enable All", callback_data="alerts_on"),
                InlineKeyboardButton("🔕 Disable All", callback_data="alerts_off")
            ],
            [
                InlineKeyboardButton("✅ Done", callback_data="alerts_done")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        msg = f"""
{EMOJI['bell']} **Alert Configuration**

Configure your notification preferences.

Current Status: {'Enabled' if True else 'Disabled'}
        """
        
        await update.message.reply_text(
            msg,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help message"""
        help_text = f"""
📖 **Anubis Bot Help**

**Tracking Commands:**
- `/track <wallet>` - Start tracking a developer
- `/list` - Show all tracked wallets
- `/stats <wallet>` - Detailed developer stats

**Discovery Commands:**
- `/recent` - Recent token launches
- `/top` - Top performing developers

**Settings:**
- `/alerts` - Configure notifications
- `/help` - Show this help message

**Tips:**
- Track wallets with 5+ successful launches
- Watch for inflows > 5 SOL
- Best launches happen within 30 min of inflow

**Support:** @anubis_support
**Version:** {ANUBIS_VERSION}
        """
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "recent":
                # Show recent launches
                if self.db:
                    launches = await self.db.get_recent_launches(hours=6)
                    
                    if not launches:
                        msg = "No launches in the last 6 hours."
                    else:
                        msg = f"{EMOJI['rocket']} **Recent Launches (6h)**\n\n"
                        for launch in launches[:5]:
                            time_str = launch['launch_time']
                            if hasattr(time_str, 'strftime'):
                                time_str = time_str.strftime('%H:%M')
                            creator = launch['creator_wallet'][:8] + "..."
                            msg += f"• {time_str} - by {creator}\n"
                else:
                    msg = "Database unavailable."
                
                await query.message.reply_text(msg, parse_mode='Markdown')
            
            elif data == "top_devs":
                msg = f"{EMOJI['fire']} **Top Developers**\n\nFeature coming soon!"
                await query.message.reply_text(msg, parse_mode='Markdown')
            
            elif data == "guide":
                guide_text = """
📖 **Quick Start Guide**

1️⃣ **Find Good Developers:**
   • Use `/top` to see best performers
   • Look for 60%+ success rate
   
2️⃣ **Track Wallets:**
   • `/track <wallet_address>`
   • Start with 3-5 wallets
   
3️⃣ **Watch for Signals:**
   • 🟢 Inflows > 5 SOL
   • 🔴 Immediate large outflows
   
4️⃣ **Act Fast:**
   • Buy within 30 seconds of launch
   • Set stop losses at -50%

Good luck! 🚀
                """
                await query.edit_message_text(guide_text, parse_mode='Markdown')
            
            elif data == "settings":
                await query.edit_message_text(
                    "⚙️ Settings menu coming soon!",
                    parse_mode='Markdown'
                )
            
            elif data == "alerts_on":
                await query.answer("✅ Alerts enabled!", show_alert=False)
            
            elif data == "alerts_off":
                await query.answer("🔕 Alerts disabled!", show_alert=False)
            
            elif data == "alerts_done":
                await query.edit_message_text(
                    "✅ Alert settings saved!",
                    parse_mode='Markdown'
                )
                
        except Exception as e:
            logger.error(f"Error in button_callback: {e}")
            await query.answer("An error occurred. Please try again.", show_alert=True)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle direct messages (wallet addresses)"""
        try:
            message_text = update.message.text.strip()
            
            # Check if it looks like a Solana address
            if 32 <= len(message_text) <= 44 and message_text.isalnum():
                # Treat as wallet address
                context.args = [message_text]
                await self.track_command(update, context)
            else:
                await update.message.reply_text(
                    "Send me a Solana wallet address to track, or use /help for commands.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error in handle_message: {e}")
    
    async def error_handler(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global error handler with detailed diagnostics"""
        error = context.error
        error_type = type(error).__name__
        
        # Get traceback
        tb_list = traceback.format_exception(type(error), error, error.__traceback__)
        tb_string = ''.join(tb_list)
        
        # Extract error location
        if error.__traceback__:
            tb = error.__traceback__
            while tb.tb_next:
                tb = tb.tb_next
            error_file = tb.tb_frame.f_code.co_filename
            error_line = tb.tb_lineno
            error_function = tb.tb_frame.f_code.co_name
        else:
            error_file = "Unknown"
            error_line = 0
            error_function = "Unknown"
        
        # Log the error
        logger.error(f"""
ERROR DETECTED
Location: {error_file}:{error_line} in {error_function}()
Type: {error_type}
Message: {str(error)}
Traceback:
{tb_string}
        """)
        
        # Send user-friendly error message
        if update and update.effective_message:
            user_message = self.get_user_friendly_error(error_type, str(error))
            try:
                await update.effective_message.reply_text(
                    f"{EMOJI['warning']} {user_message}",
                    parse_mode='Markdown'
                )
            except:
                pass  # Avoid error loop
        
        # Send detailed error to admin if configured
        if ADMIN_TELEGRAM_ID and update:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=f"🚨 Error: {error_type} at line {error_line}\n{str(error)[:200]}",
                    parse_mode='Markdown'
                )
            except:
                pass
    
    def get_user_friendly_error(self, error_type: str, error_str: str) -> str:
        """Convert technical errors to user-friendly messages"""
        
        error_messages = {
            'ConnectionError': "Connection issue. Please try again.",
            'TimeoutError': "Request timed out. Please try again.",
            'ValueError': "Invalid input. Please check your command.",
            'AttributeError': "Feature temporarily unavailable.",
        }
        
        # Check for specific error patterns
        error_lower = error_str.lower()
        if 'database' in error_lower:
            return "Database temporarily unavailable. Some features may be limited."
        elif 'address' in error_lower:
            return "Invalid wallet address format. Please check and try again."
        elif 'connection' in error_lower:
            return "Connection issue detected. Please try again."
        
        return error_messages.get(error_type, "An error occurred. Please try again or use /help.")
    
    async def send_error_message(self, update: Update, action: str) -> None:
        """Send a generic error message"""
        await update.message.reply_text(
            f"{EMOJI['warning']} Error while {action}. Please try again or contact support.",
            parse_mode='Markdown'
        )
    
    def run(self):
        """Start the bot"""
        # Build application with proper initialization
        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )
        
        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("track", self.track_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("recent", self.recent_command))
        self.application.add_handler(CommandHandler("top", self.top_command))
        self.application.add_handler(CommandHandler("alerts", self.alerts_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("admin_scan", self.admin_scan_command))

        # Register callback handler for buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Register message handler for direct wallet addresses
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Register error handler
        self.application.add_error_handler(self.error_handler)
        
        # Start bot
        logger.info(f"🚀 Starting Anubis Bot v{ANUBIS_VERSION} in {ENVIRONMENT} mode...")
        
        # Use polling (works everywhere)
        self.application.run_polling(drop_pending_updates=True)

def main():
    """Main function"""
    try:
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        bot = AnubisBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()