"""
Anubis Bot - Main Telegram Interface (Fixed)
"""

import os
import asyncio
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
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
from database import Database
from pump_monitor import PumpFunMonitor

load_dotenv()

class AnubisBot:
    """Main bot class - all data from database"""
    
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.db = Database(os.getenv('DATABASE_URL'))
        self.pump_monitor = None
        self.application = None
        self.monitor_task = None
        
    async def post_init(self, application: Application) -> None:
        """Initialize after application is created"""
        await self.db.connect()
        
        # Initialize Pump.fun monitor
        self.pump_monitor = PumpFunMonitor(
            os.getenv('SOLANA_RPC_URL'),
            self.db
        )
        
        # Start monitoring in background
        self.monitor_task = asyncio.create_task(self.pump_monitor.start_monitoring())
        logger.info("Bot initialization complete")
    
    async def post_shutdown(self, application: Application) -> None:
        """Cleanup on shutdown"""
        if self.monitor_task:
            self.monitor_task.cancel()
        
        if self.pump_monitor:
            await self.pump_monitor.stop_monitoring()
        
        await self.db.disconnect()
        logger.info("Bot shutdown complete")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Save user to database
        await self.db.upsert_user(
            user.id,
            username=user.username,
            first_name=user.first_name
        )
        
        message = f"""
🚀 **Welcome to Anubis Bot**

I track Solana developer wallets and alert you to new token launches.

**Available Commands:**
/track `<wallet>` - Track a developer wallet
/list - Show your tracked wallets
/stats `<wallet>` - Get developer statistics
/recent - Show recent launches
/help - Show help

Start by tracking a wallet address!
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Recent Launches", callback_data="recent"),
                InlineKeyboardButton("❓ Help", callback_data="help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def track_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track a developer wallet"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text(
                "Please provide a wallet address:\n`/track <wallet_address>`",
                parse_mode='Markdown'
            )
            return
        
        wallet_address = context.args[0]
        
        # Basic validation (32-44 chars)
        if not (32 <= len(wallet_address) <= 44):
            await update.message.reply_text(
                "❌ Invalid Solana address format",
                parse_mode='Markdown'
            )
            return
        
        # Track the wallet
        success = await self.db.track_wallet(user_id, wallet_address)
        
        if success:
            # Check if we have data on this developer
            developer = await self.db.get_developer(wallet_address)
            
            if developer and developer['total_launches'] > 0:
                msg = f"""
✅ **Tracking Started**

Address: `{wallet_address[:8]}...{wallet_address[-8:]}`

**Developer Stats:**
- Total Launches: {developer['total_launches']}
- Success Rate: {developer['success_rate']:.1f}%
- Last Active: {developer['last_active'].strftime('%Y-%m-%d') if developer['last_active'] else 'Unknown'}

You'll receive alerts for new launches.
                """
            else:
                msg = f"""
✅ **Tracking Started**

Address: `{wallet_address[:8]}...{wallet_address[-8:]}`

No historical data yet. I'll alert you when this wallet launches tokens.
                """
            
            await update.message.reply_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(
                "❌ Failed to track wallet. Please try again.",
                parse_mode='Markdown'
            )
    
    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List tracked wallets"""
        user_id = update.effective_user.id
        wallets = await self.db.get_tracked_wallets(user_id)
        
        if not wallets:
            await update.message.reply_text(
                "You're not tracking any wallets yet.\nUse `/track <wallet>` to start!",
                parse_mode='Markdown'
            )
            return
        
        msg = "📊 **Your Tracked Wallets**\n\n"
        
        for wallet in wallets:
            addr = wallet['wallet_address']
            alias = wallet['alias'] or f"{addr[:8]}...{addr[-8:]}"
            
            # Add actual stats if available
            launches = wallet.get('total_launches', 0)
            success_rate = wallet.get('success_rate', 0)
            
            if launches > 0:
                msg += f"• `{alias}`\n  Launches: {launches} | Success: {success_rate:.1f}%\n\n"
            else:
                msg += f"• `{alias}`\n  No launch data yet\n\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show developer statistics"""
        if not context.args:
            await update.message.reply_text(
                "Please provide a wallet address:\n`/stats <wallet_address>`",
                parse_mode='Markdown'
            )
            return
        
        wallet_address = context.args[0]
        
        # Get developer data
        developer = await self.db.get_developer(wallet_address)
        
        if not developer or developer['total_launches'] == 0:
            await update.message.reply_text(
                f"No data available for this wallet.\nAddress: `{wallet_address[:8]}...{wallet_address[-8:]}`",
                parse_mode='Markdown'
            )
            return
        
        # Get pattern analysis
        patterns = await self.pump_monitor.analyze_developer_patterns(wallet_address)
        
        msg = f"""
📈 **Developer Statistics**

Wallet: `{wallet_address[:8]}...{wallet_address[-8:]}`

**Launch History:**
- Total Launches: {developer['total_launches']}
- Successful: {developer['successful_launches']}
- Success Rate: {developer['success_rate']:.1f}%

**Financial Performance:**
- Total Earnings: ${developer['total_earnings']:,.0f}
- Average Earnings: ${developer['average_earnings']:,.0f}
- Highest ATH: ${developer['highest_ath']:,.0f}
        """
        
        if patterns.get('preferred_hour') is not None:
            msg += f"""

**Patterns Detected:**
- Preferred Launch Hour: {patterns['preferred_hour']:02d}:00 UTC
- Preferred Day: {patterns.get('preferred_day', 'Unknown')}
- Avg Initial Liquidity: {patterns.get('avg_liquidity', 0):.2f} SOL
            """
        
        if developer['last_launch_time']:
            msg += f"\n\nLast Launch: {developer['last_launch_time'].strftime('%Y-%m-%d %H:%M')} UTC"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def recent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent launches"""
        launches = await self.db.get_recent_launches(hours=24)
        
        if not launches:
            await update.message.reply_text(
                "No launches detected in the last 24 hours.",
                parse_mode='Markdown'
            )
            return
        
        msg = "🚀 **Recent Launches (24h)**\n\n"
        
        for launch in launches[:10]:  # Show max 10
            time_str = launch['launch_time'].strftime('%H:%M')
            creator = launch['creator_wallet'][:8] + "..."
            
            msg += f"• {time_str} - "
            if launch.get('token_symbol'):
                msg += f"${launch['token_symbol']} "
            msg += f"by {creator}\n"
            
            if launch.get('initial_liquidity_sol'):
                msg += f"  Liquidity: {launch['initial_liquidity_sol']:.2f} SOL\n"
            
            msg += "\n"
        
        await update.message.reply_text(msg, parse_mode='Markdown')
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "recent":
            launches = await self.db.get_recent_launches(hours=6)
            
            if not launches:
                msg = "No launches in the last 6 hours."
            else:
                msg = "🚀 **Recent Launches (6h)**\n\n"
                for launch in launches[:5]:
                    time_str = launch['launch_time'].strftime('%H:%M')
                    creator = launch['creator_wallet'][:8] + "..."
                    msg += f"• {time_str} - by {creator}\n"
            
            await query.message.reply_text(msg, parse_mode='Markdown')
        
        elif query.data == "help":
            help_text = """
📖 **How to Use Anubis Bot**

1. **Track Developers**: Use `/track <wallet>` to monitor wallets
2. **Get Alerts**: Receive notifications for new launches
3. **View Stats**: Use `/stats <wallet>` for developer metrics
4. **Check Activity**: Use `/recent` for latest launches

The bot monitors Pump.fun in real-time and builds developer profiles based on actual on-chain data.
            """
            await query.message.reply_text(help_text, parse_mode='Markdown')
    
    def run(self):
        """Start the bot with proper async handling"""
        # Build application with post_init and post_shutdown
        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )
        
        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("track", self.track_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("recent", self.recent_command))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Start bot with polling
        logger.info("Starting Anubis Bot...")
        self.application.run_polling(drop_pending_updates=True)

async def main():
    """Main entry point"""
    bot = AnubisBot()
    await bot.initialize()
    bot.run()

if __name__ == "__main__":
    bot = AnubisBot()
    bot.run()  # run() handles everything