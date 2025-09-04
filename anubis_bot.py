import os
import logging
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

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration from environment
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ENVIRONMENT = os.getenv('BOT_ENV', 'development')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Anubis bot version
ANUBIS_VERSION = "1.0.0"

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
    'siren': '🚨'
}

class AnubisBot:
    """Main Anubis Bot class for tracking Solana developers"""
    
    def __init__(self):
        self.application = None
        self.start_time = datetime.now()
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a message when the command /start is issued."""
        user = update.effective_user
        welcome_message = f"""
{EMOJI['rocket']} **Welcome to Anubis Bot** {EMOJI['eye']}

Track Solana developer wallets and get alerts on:
- {EMOJI['money']} Wallet inflows (potential launches)
- {EMOJI['rocket']} New token launches
- {EMOJI['chart']} Developer success metrics
- {EMOJI['fire']} High-potential opportunities

**Available Commands:**
/track `<wallet>` - Track a developer wallet
/untrack `<wallet>` - Stop tracking a wallet
/list - Show your tracked wallets
/stats `<wallet>` - Get developer statistics
/top - Show top performing developers
/alerts - Configure alert settings
/help - Show detailed help

**Quick Start:**
Send me a Solana wallet address to start tracking!

Version: {ANUBIS_VERSION}
Environment: {ENVIRONMENT}
        """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("📊 Top Devs", callback_data="top_devs"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📖 Guide", callback_data="guide"),
                InlineKeyboardButton("💬 Support", url="https://t.me/anubis_support")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Log user start
        logger.info(f"User {user.id} (@{user.username}) started the bot")

    async def track_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Track a developer wallet"""
        user = update.effective_user
        
        if not context.args:
            await update.message.reply_text(
                f"{EMOJI['warning']} Please provide a wallet address:\n"
                "`/track <wallet_address>`",
                parse_mode='Markdown'
            )
            return
        
        wallet_address = context.args[0]
        
        # Basic Solana address validation (32-44 chars, base58)
        if not (32 <= len(wallet_address) <= 44):
            await update.message.reply_text(
                f"{EMOJI['cross']} Invalid Solana wallet address!\n"
                "Addresses should be 32-44 characters long.",
                parse_mode='Markdown'
            )
            return
        
        # TODO: Add database check for existing tracking
        # TODO: Add Solana RPC validation
        
        # For now, just confirm
        await update.message.reply_text(
            f"{EMOJI['check']} **Wallet Tracked Successfully!**\n\n"
            f"Address: `{wallet_address[:8]}...{wallet_address[-8:]}`\n"
            f"Status: Active\n"
            f"Alerts: Enabled\n\n"
            f"You'll receive alerts for:\n"
            f"• Inflows > 1 SOL\n"
            f"• New token launches\n"
            f"• Significant events",
            parse_mode='Markdown'
        )
        
        logger.info(f"User {user.id} tracking wallet: {wallet_address}")

    async def untrack_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Stop tracking a wallet"""
        if not context.args:
            await update.message.reply_text(
                f"{EMOJI['warning']} Please provide a wallet address:\n"
                "`/untrack <wallet_address>`",
                parse_mode='Markdown'
            )
            return
        
        wallet_address = context.args[0]
        
        # TODO: Remove from database
        
        await update.message.reply_text(
            f"{EMOJI['check']} Stopped tracking wallet:\n`{wallet_address}`",
            parse_mode='Markdown'
        )

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List all tracked wallets for user"""
        user = update.effective_user
        
        # TODO: Fetch from database
        # For now, show example
        
        message = f"""
{EMOJI['eye']} **Your Tracked Wallets**

1. `7xKXtg...3wmTYKp` {EMOJI['check']}
   Success Rate: 75% | Launches: 12
   
2. `9aHzJk...8nBqLx2` {EMOJI['check']}
   Success Rate: 60% | Launches: 8
   
3. `4bNmPq...7xKlMn9` {EMOJI['warning']}
   Success Rate: 30% | Launches: 15

Total: 3 wallets tracked
        """
        
        await update.message.reply_text(message, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show detailed stats for a developer wallet"""
        if not context.args:
            await update.message.reply_text(
                f"{EMOJI['warning']} Please provide a wallet address:\n"
                "`/stats <wallet_address>`",
                parse_mode='Markdown'
            )
            return
        
        wallet_address = context.args[0]
        
        # TODO: Fetch real stats from database
        # Example stats for now
        
        stats_message = f"""
{EMOJI['chart']} **Developer Stats**

Wallet: `{wallet_address[:8]}...{wallet_address[-8:]}`

**Performance Metrics:**
- Total Launches: 15
- Successful: 10 ({EMOJI['check']} 66.7%)
- Rugged: 3 ({EMOJI['skull']} 20%)
- Active: 2 ({EMOJI['fire']} 13.3%)

**Top 5 Launches:**
1. $PEPE2 - 450x return {EMOJI['gem']}
2. $MOON - 125x return {EMOJI['rocket']}
3. $DOGE3 - 85x return {EMOJI['money']}
4. $SHIB5 - 45x return
5. $FLOKI - 12x return

**Recent Activity:**
- Last launch: 2 hours ago
- Last inflow: 5.2 SOL (30 min ago)
- Avg time to rug: 4.5 hours
- Success probability: 68%

**Anubis Score: 7.8/10** {EMOJI['fire']}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh_stats:{wallet_address[:8]}"),
                InlineKeyboardButton("🔔 Set Alert", callback_data=f"set_alert:{wallet_address[:8]}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            stats_message, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def top_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show top performing developers"""
        
        # TODO: Fetch from database
        # Example for now
        
        top_message = f"""
{EMOJI['fire']} **Top Performing Developers**
*Last 7 Days*

**1.** `8xNm2p...9kLmX3` {EMOJI['gem']}
   Score: 9.5/10 | Launches: 8
   Avg Return: 125x | Success: 87%

**2.** `3bKj7x...2mNpQ8` {EMOJI['rocket']}
   Score: 8.9/10 | Launches: 12
   Avg Return: 85x | Success: 75%

**3.** `7yHm4k...5xPqL2`
   Score: 8.2/10 | Launches: 6
   Avg Return: 95x | Success: 83%

**4.** `2nMx9p...8kJmL7`
   Score: 7.8/10 | Launches: 15
   Avg Return: 45x | Success: 60%

**5.** `9xLm3k...4nPqB2`
   Score: 7.5/10 | Launches: 9
   Avg Return: 55x | Success: 66%

_Updated: {datetime.now().strftime('%H:%M UTC')}_
        """
        
        await update.message.reply_text(top_message, parse_mode='Markdown')

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Configure alert settings"""
        
        keyboard = [
            [
                InlineKeyboardButton("💰 Inflow Threshold", callback_data="alert_inflow"),
                InlineKeyboardButton("📊 Min Score", callback_data="alert_score")
            ],
            [
                InlineKeyboardButton("🔔 All Alerts ON", callback_data="alerts_on"),
                InlineKeyboardButton("🔕 All Alerts OFF", callback_data="alerts_off")
            ],
            [
                InlineKeyboardButton("✅ Done", callback_data="alerts_done")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"""
⚙️ **Alert Configuration**

Current Settings:
- Inflow Threshold: 1.0 SOL
- Min Developer Score: 5.0/10
- Launch Alerts: Enabled
- Rug Warnings: Enabled

Select what to configure:
        """
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help message"""
        help_text = f"""
📖 **Anubis Bot Help**

**Tracking Commands:**
- `/track <wallet>` - Start tracking a developer
- `/untrack <wallet>` - Stop tracking
- `/list` - Show all tracked wallets
- `/stats <wallet>` - Detailed developer stats

**Discovery Commands:**
- `/top` - Top performing developers
- `/trending` - Trending launches
- `/risky` - High risk/reward devs

**Alert Commands:**
- `/alerts` - Configure notifications
- `/mute` - Temporarily disable alerts
- `/unmute` - Re-enable alerts

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
        
        if data == "top_devs":
            top_message = f"""... the message ..."""
            await query.message.reply_text(top_message, parse_mode='Markdown')  # ✅ This works!)
        
        elif data == "settings":
            await query.edit_message_text(
                "⚙️ Settings menu coming soon!",
                parse_mode='Markdown'
            )
        
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
   • 🟢 Multiple small inflows
   • 🔴 Immediate large outflows
   
4️⃣ **Act Fast:**
   • Buy within 30 seconds of launch
   • Set stop losses at -50%
   • Take profits at 2-5x

Good luck! 🚀
            """
            await query.edit_message_text(guide_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle direct messages (wallet addresses)"""
        message_text = update.message.text
        
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

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                f"{EMOJI['warning']} An error occurred. Please try again or contact support.",
                parse_mode='Markdown'
            )

    def run(self):
        """Start the bot"""
        
        # Create application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("track", self.track_command))
        self.application.add_handler(CommandHandler("untrack", self.untrack_command))
        self.application.add_handler(CommandHandler("list", self.list_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("top", self.top_command))
        self.application.add_handler(CommandHandler("alerts", self.alerts_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Register callback handler for buttons
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Register message handler for direct wallet addresses
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        
        # Register error handler
        self.application.add_error_handler(self.error_handler)
        
        # Start bot
        logger.info(f"Starting Anubis Bot v{ANUBIS_VERSION} in {ENVIRONMENT} mode...")
        
        if ENVIRONMENT == 'production':
            # Production mode - use webhook for DigitalOcean
            port = int(os.environ.get('PORT', 8443))
            webhook_url = os.environ.get('WEBHOOK_URL')  # You'll set this later
            
            if webhook_url:
                self.application.run_webhook(
                    listen='0.0.0.0',
                    port=port,
                    webhook_url=webhook_url
                )
            else:
                # Fallback to polling
                self.application.run_polling(drop_pending_updates=True)
        else:
            # Development mode - use polling
            self.application.run_polling(drop_pending_updates=True)

async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "top_devs":
        # Show top devs directly in the callback
        top_message = f"""
{EMOJI['fire']} **Top Performing Developers**
*Last 7 Days*

**1.** `8xNm2p...9kLmX3` {EMOJI['gem']}
   Score: 9.5/10 | Launches: 8
   Avg Return: 125x | Success: 87%

**2.** `3bKj7x...2mNpQ8` {EMOJI['rocket']}
   Score: 8.9/10 | Launches: 12
   Avg Return: 85x | Success: 75%

**3.** `7yHm4k...5xPqL2`
   Score: 8.2/10 | Launches: 6
   Avg Return: 95x | Success: 83%

_Updated: {datetime.now().strftime('%H:%M UTC')}_
        """
        await query.message.reply_text(top_message, parse_mode='Markdown')
    
    elif data == "settings":
        settings_keyboard = [
            [
                InlineKeyboardButton("💰 Inflow Threshold", callback_data="alert_inflow"),
                InlineKeyboardButton("📊 Min Score", callback_data="alert_score")
            ],
            [
                InlineKeyboardButton("🔔 Alerts ON", callback_data="alerts_on"),
                InlineKeyboardButton("🔕 Alerts OFF", callback_data="alerts_off")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(settings_keyboard)
        
        await query.edit_message_text(
            "⚙️ **Settings**\n\nConfigure your alert preferences:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
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
   • 🟢 Multiple small inflows
   • 🔴 Immediate large outflows
   
4️⃣ **Act Fast:**
   • Buy within 30 seconds of launch
   • Set stop losses at -50%
   • Take profits at 2-5x

Good luck! 🚀
        """
        back_keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(back_keyboard)
        
        await query.edit_message_text(
            guide_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == "back_to_main":
        # Go back to main menu
        welcome_message = f"""
{EMOJI['rocket']} **Welcome to Anubis Bot** {EMOJI['eye']}

Track Solana developer wallets and get alerts on:
- {EMOJI['money']} Wallet inflows (potential launches)
- {EMOJI['rocket']} New token launches
- {EMOJI['chart']} Developer success metrics
- {EMOJI['fire']} High-potential opportunities

Version: {ANUBIS_VERSION}
        """
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Top Devs", callback_data="top_devs"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings")
            ],
            [
                InlineKeyboardButton("📖 Guide", callback_data="guide"),
                InlineKeyboardButton("💬 Support", url="https://t.me/anubis_support")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    elif data == "alert_inflow":
        await query.answer("Feature coming soon: Set your minimum SOL inflow threshold", show_alert=True)
    
    elif data == "alert_score":
        await query.answer("Feature coming soon: Set minimum developer score for alerts", show_alert=True)
    
    elif data == "alerts_on":
        await query.answer("✅ Alerts enabled!", show_alert=False)
        # TODO: Save to database
    
    elif data == "alerts_off":
        await query.answer("🔕 Alerts disabled!", show_alert=False)
        # TODO: Save to database
    
    elif data.startswith("refresh_stats:"):
        wallet = data.split(":")[1]
        await query.answer(f"♻️ Refreshing stats for {wallet}...", show_alert=False)
        # TODO: Actually refresh from blockchain
    
    elif data.startswith("set_alert:"):
        wallet = data.split(":")[1]
        await query.answer(f"🔔 Alert set for wallet {wallet}", show_alert=True)
        # TODO: Save alert preference

def main():
    """Main function"""
    if not BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN found! Please check your .env file")
        return
    
    try:
        bot = AnubisBot()
        bot.run()
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()