"""
Enhanced Error Handler for Anubis Bot
Add this to your bot.py file
"""

import traceback
import sys
from datetime import datetime
from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes
from loguru import logger

class ErrorHandler:
    """Comprehensive error handling with detailed diagnostics"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.admin_chat_id = os.getenv('ADMIN_TELEGRAM_ID')  # Optional: your Telegram ID for error alerts
        
        # Configure detailed logging
        logger.remove()  # Remove default handler
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
    
    async def handle_error(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        """Global error handler with detailed diagnostics"""
        
        # Get the error details
        error = context.error
        error_type = type(error).__name__
        error_module = type(error).__module__
        
        # Get traceback
        tb_list = traceback.format_exception(type(error), error, error.__traceback__)
        tb_string = ''.join(tb_list)
        
        # Extract specific error location
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
        
        # Create detailed error report
        error_report = f"""
🚨 ERROR DETECTED 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 Location:
   File: {error_file}
   Function: {error_function}()
   Line: {error_line}

❌ Error Type: {error_module}.{error_type}
💬 Message: {str(error)}

📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """
        
        # Log the full error
        logger.error(f"{error_report}\n\n📋 Full Traceback:\n{tb_string}")
        
        # Handle specific error types with helpful messages
        user_message = await self.get_user_friendly_message(error, error_type)
        
        # Send error to user if update exists
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    f"❌ {user_message}\n\n"
                    f"Error Code: `{error_type}_{error_line}`\n"
                    f"Please try again or contact support.",
                    parse_mode='Markdown'
                )
            except:
                pass  # Avoid error loop if sending fails
        
        # Send detailed error to admin (optional)
        if self.admin_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=self.admin_chat_id,
                    text=f"```\n{error_report}\n```",
                    parse_mode='Markdown'
                )
            except:
                pass
        
        # Handle critical errors that should restart the bot
        if self.is_critical_error(error):
            logger.critical(f"CRITICAL ERROR - Bot may need restart: {error_type}")
            # Optionally trigger a restart or alert
    
    async def get_user_friendly_message(self, error: Exception, error_type: str) -> str:
        """Convert technical errors to user-friendly messages"""
        
        error_messages = {
            # Database errors
            'ConnectionError': "Database connection issue. Please try again in a moment.",
            'OperationalError': "Database is temporarily unavailable.",
            'IntegrityError': "Data conflict detected. This wallet may already be tracked.",
            
            # Redis errors
            'RedisError': "Cache system issue. Performance may be degraded.",
            'ConnectionRefusedError': "Cannot connect to cache service.",
            
            # Solana/RPC errors
            'JSONRPCError': "Blockchain connection issue. Please try again.",
            'SolanaRpcException': "Cannot reach Solana network.",
            'TimeoutError': "Request timed out. The network may be congested.",
            
            # Telegram errors
            'NetworkError': "Network connection issue.",
            'BadRequest': "Invalid request format.",
            'Unauthorized': "Bot authorization issue.",
            'MessageNotModified': "No changes to update.",
            'MessageToDeleteNotFound': "Message already deleted.",
            
            # Input validation
            'ValueError': "Invalid input provided. Please check your command.",
            'KeyError': "Missing required data.",
            'AttributeError': "Internal configuration issue.",
            
            # Rate limiting
            'RetryAfterError': f"Rate limited. Please wait {getattr(error, 'retry_after', 60)} seconds.",
        }
        
        # Check for specific error strings
        error_str = str(error).lower()
        if 'address' in error_str:
            return "Invalid wallet address format. Please check and try again."
        elif 'connection' in error_str:
            return "Connection issue detected. Retrying..."
        elif 'timeout' in error_str:
            return "Request timed out. Please try again."
        elif 'permission' in error_str:
            return "Permission denied. Please check bot settings."
        
        return error_messages.get(error_type, f"An unexpected error occurred: {error_type}")
    
    def is_critical_error(self, error: Exception) -> bool:
        """Identify errors that require bot restart"""
        critical_errors = [
            'AsyncIOError',
            'SystemExit',
            'KeyboardInterrupt',
            'RuntimeError',
            'MemoryError',
        ]
        return type(error).__name__ in critical_errors
    
    async def startup_check(self) -> dict:
        """Run startup diagnostics to catch configuration issues early"""
        checks = {
            'telegram_token': False,
            'database': False,
            'redis': False,
            'solana_rpc': False
        }
        errors = []
        
        # Check Telegram token
        try:
            if os.getenv('TELEGRAM_BOT_TOKEN'):
                checks['telegram_token'] = True
            else:
                errors.append("❌ TELEGRAM_BOT_TOKEN not set in environment")
        except Exception as e:
            errors.append(f"❌ Telegram token check failed: {e}")
        
        # Check database connection
        try:
            if self.bot.db:
                await self.bot.db.pool.fetchval("SELECT 1")
                checks['database'] = True
                logger.info("✅ Database connection verified")
        except Exception as e:
            errors.append(f"❌ Database connection failed: {e}")
            logger.error(f"Database check failed: {e}")
        
        # Check Redis (if configured)
        try:
            redis_url = os.getenv('REDIS_URL')
            if redis_url and redis_url != 'redis://localhost:6379':
                # Only check if Redis is actually configured
                import aioredis
                redis = await aioredis.from_url(redis_url)
                await redis.ping()
                await redis.close()
                checks['redis'] = True
                logger.info("✅ Redis connection verified")
        except:
            # Redis is optional, so just log
            logger.warning("⚠️ Redis not available - caching disabled")
        
        # Check Solana RPC
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    os.getenv('SOLANA_RPC_URL'),
                    json={"jsonrpc": "2.0", "id": 1, "method": "getHealth"}
                )
                if response.status_code == 200:
                    checks['solana_rpc'] = True
                    logger.info("✅ Solana RPC connection verified")
        except Exception as e:
            errors.append(f"❌ Solana RPC check failed: {e}")
        
        # Log startup report
        logger.info("="*50)
        logger.info("STARTUP DIAGNOSTICS COMPLETE")
        logger.info(f"✅ Passed: {sum(checks.values())}/{len(checks)}")
        for service, status in checks.items():
            logger.info(f"  {service}: {'✅' if status else '❌'}")
        
        if errors:
            logger.error("STARTUP ERRORS DETECTED:")
            for error in errors:
                logger.error(f"  {error}")
        logger.info("="*50)
        
        return {'checks': checks, 'errors': errors}


# Integration with your AnubisBot class:
class AnubisBot:
    """Add this to your existing AnubisBot class"""
    
    def __init__(self):
        # ... existing code ...
        self.error_handler = ErrorHandler(self)
    
    async def post_init(self, application: Application) -> None:
        """Enhanced initialization with error checking"""
        try:
            # Run startup diagnostics
            startup_results = await self.error_handler.startup_check()
            
            if startup_results['errors']:
                logger.warning(f"Starting with {len(startup_results['errors'])} issues")
            
            # Continue with normal initialization
            await self.db.connect()
            
            # Initialize Pump.fun monitor with error handling
            try:
                self.pump_monitor = PumpFunMonitor(
                    os.getenv('SOLANA_RPC_URL'),
                    self.db
                )
                self.monitor_task = asyncio.create_task(
                    self.monitor_with_error_handling()
                )
            except Exception as e:
                logger.error(f"Failed to start Pump.fun monitor: {e}")
                # Bot can still run without monitor
            
            logger.info("✅ Bot initialization complete")
            
        except Exception as e:
            logger.critical(f"FAILED TO INITIALIZE BOT: {e}")
            raise
    
    async def monitor_with_error_handling(self):
        """Wrapped monitor task with error recovery"""
        while True:
            try:
                await self.pump_monitor.start_monitoring()
            except Exception as e:
                logger.error(f"Monitor crashed: {e}. Restarting in 30 seconds...")
                await asyncio.sleep(30)
    
    def run(self):
        """Start the bot with error handling"""
        self.application = (
            Application.builder()
            .token(self.token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )
        
        # Add the error handler
        self.application.add_error_handler(self.error_handler.handle_error)
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