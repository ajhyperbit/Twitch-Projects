"""
Custom .env file loader.

Parses .env files and loads them into os.environ. Supports:
- Comments (lines starting with #)
- Inline comments (values with # followed by comment text)
- Key=value pairs

Example .env file:
    TWITCH_CLIENT_ID=abc123
    DEBUG=1  # Enable debug mode
    # This is a comment
"""

import os

def load_dotenv(filepath=".env"):
    """
    Load environment variables from a .env file.
    
    Ignores comments (both full-line and inline) and strips whitespace.
    Inline comments are separated from values using '#'.
    
    Args:
        filepath (str): Path to the .env file (default: ".env")
        
    Example:
        load_dotenv(".env")
        value = os.getenv("MY_VAR")
    """
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                # Strip inline comments from value using partition for clarity
                value = value.partition("#")[0].strip()
                os.environ.setdefault(key, value)
    except FileNotFoundError:
        print(f".env file '{filepath}' not found.")