#!/usr/bin/env python3
"""
Anubis Bot - Main Entry Point (Fixed)
"""

import sys
import logging
from anubis_bot import AnubisBot

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function - synchronous entry point"""
    logger.info("Starting Anubis Bot System...")
    
    try:
        bot = AnubisBot()
        # Don't use asyncio.run() here - let the bot handle its own event loop
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()