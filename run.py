#!/usr/bin/env python3
"""
Anubis Bot - Main Entry Point
"""

import asyncio
import sys
import logging

# Configure basic logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d - %(message)s'
)

# Try to import loguru, fall back to standard logging
try:
    from loguru import logger
    # Configure loguru
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
except ImportError:
    # Use standard logging as fallback
    logger = logging.getLogger(__name__)
    logger.warning("Loguru not installed, using standard logging")

async def main():
    """Main function"""
    logger.info("Starting Anubis Bot System...")
    
    try:
        from bot import AnubisBot
        bot = AnubisBot()
        await bot.initialize()
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())