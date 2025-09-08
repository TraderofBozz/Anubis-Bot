"""
Module for handling missing imports reporting
"""
from loguru import logger

def check_imports():
    """Check and report missing imports"""
    required_modules = [
        'telegram',
        'asyncpg',
        'loguru',
        'reportlab',
        'solana'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        logger.error(f"Missing modules: {missing}")
    return missing