import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("=" * 50)
print("ENVIRONMENT DEBUG")
print("=" * 50)

# Show current working directory
print(f"Current directory: {os.getcwd()}")
print(f"Script location: {os.path.dirname(os.path.abspath(__file__))}")

# Check if .env exists
env_path = Path('.') / '.env'
print(f"\n.env file exists: {env_path.exists()}")
print(f".env absolute path: {env_path.absolute()}")

# Try to load .env
load_dotenv(verbose=True)

# Check what's in environment
print("\n" + "=" * 50)
print("CHECKING ENVIRONMENT VARIABLES")
print("=" * 50)

# Method 1: Direct check
token = os.getenv('TELEGRAM_BOT_TOKEN')
print(f"TELEGRAM_BOT_TOKEN exists: {token is not None}")
if token:
    print(f"Token length: {len(token)} characters")
    print(f"Token preview: {token[:10]}...{token[-5:]}")
else:
    print("Token is None or empty")

# Method 2: Check all env vars that contain 'TELEGRAM'
print("\nAll TELEGRAM-related environment variables:")
telegram_vars = {k: v for k, v in os.environ.items() if 'TELEGRAM' in k or 'BOT' in k}
for key, value in telegram_vars.items():
    print(f"  {key}: {value[:20]}..." if len(value) > 20 else f"  {key}: {value}")

# Show .env file contents (safely)
print("\n" + "=" * 50)
print(".ENV FILE CONTENTS (without sensitive data)")
print("=" * 50)

if env_path.exists():
    with open('.env', 'r') as f:
        lines = f.readlines()
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key = line.split('=')[0]
                    print(f"  Found key: {key}")
else:
    print("  .env file not found!")

# Check for common issues
print("\n" + "=" * 50)
print("COMMON ISSUES CHECK")
print("=" * 50)

# Check for .env.example instead of .env
if Path('.env.example').exists():
    print("⚠️  Found .env.example - did you forget to rename it to .env?")

# Check for spaces in .env
if env_path.exists():
    with open('.env', 'r') as f:
        content = f.read()
        if 'TELEGRAM_BOT_TOKEN =' in content or 'TELEGRAM_BOT_TOKEN= ' in content:
            print("⚠️  Warning: Spaces detected around '=' in .env file")
        if '"' in content or "'" in content:
            print("ℹ️  Note: Quotes found in .env file (usually not needed)")