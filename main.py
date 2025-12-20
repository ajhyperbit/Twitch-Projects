"""
Main entry point for Twitch integration service.
Handles multiple modes: title updates, chat listening, and queued message processing.

Modes:
    - title: Automatically updates channel title based on subscriber count
    - chat: Displays chat messages in real-time as they arrive
    - bits/message/messages: Aliases for chat mode
    - queued: Processes chat messages at a specified rate (RATE_PER_SEC)

Environment Variables:
    - mode: Operating mode (title, chat, queued)
    - BROADCASTER_USERNAME: Twitch username of the broadcaster
    - BOT_USERNAME: Twitch username of the bot account
    - RATE_PER_SEC: Messages per second for queued mode (default: 1)
    - DEBUG: Enable debug output (0 or 1)
"""

import os
import asyncio
from dotenv import load_dotenv

# Import consolidated service
from twitch_service import (
    TwitchAuth,
    get_channel_id,
    twitch_listener,
    process_messages,
    update_title_loop,
)

# Import auxiliary modules
from KeyCodes import *

# Import scopes
from scopes import SCOPES

load_dotenv()

# ===========================
# Configuration
# ===========================

MODE = os.getenv("mode", "chat").lower()
RATE_PER_SEC = int(os.getenv("RATE_PER_SEC", 1))
BROADCASTER_USERNAME = os.getenv("BROADCASTER_USERNAME", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")
DEBUG_MODE = int(os.getenv("DEBUG", 0))
TEST_COMMAND = (os.getenv("TEST_COMMAND", '!hehe'))
# Initialize auth with broadcaster ID
try:
    BROADCASTER_ID = get_channel_id(BROADCASTER_USERNAME)
    auth = TwitchAuth(scopes=SCOPES, broadcaster_id=BROADCASTER_ID)
except Exception as e:
    print(f"Error initializing: {e}")
    print("Make sure BROADCASTER_USERNAME is set correctly in .env")
    exit(1)

# ===========================
# Main Mode Handler
# ===========================

async def main():
    """Main entry point. Route to appropriate handler based on MODE."""
    auth.get_valid_token(validate=True)

    if MODE == "title":
        # Title update is sync, run in thread pool
        await asyncio.to_thread(update_title_loop, auth)
    
    elif MODE in ("chat", "bits", "message", "messages"):
        # Listen for events and display in real-time
        await process_chat_messages(auth)
    
    elif MODE == "queued":
        # Queued message processing with rate limiting
        await process_queued_messages(auth)
    
    else:
        print(f"Invalid mode: '{MODE}'")
        print("Valid modes: title, chat, bits, message, messages, queued")


# ===========================
# Message Processing
# ===========================

async def handle_chat_message(event, broadcaster_name, rate_limited=False):
    """
    Handle a single chat message event.
    
    Processes the message by:
    - Logging the message to console
    - Detecting and responding to cheers
    - Checking for broadcaster/bot commands
    - Triggering key presses on specific conditions
    
    Args:
        event (dict): The event data from Twitch EventSub containing message and cheer info
        broadcaster_name (str): Name of the broadcaster (for logging)
        rate_limited (bool): Whether this is being processed with rate limiting (for context)
    """
    user = event["chatter_user_name"].lower()
    msg_text = event["message"]["text"]
    cheer = event["cheer"]
    
    # Log message
    print(f"[Chat: {broadcaster_name}] {user}: {msg_text}")
    
    # Respond to cheer messages
    if cheer:
        cheer_amount = cheer["bits"]
        print(f"Cheer detected: {cheer_amount} bits")
        HoldAndReleaseKey(G, 0.5)
    else:
        if DEBUG_MODE:
            print("NonCheer msg")
    
    # Respond to specific users and commands
    is_broadcaster = user == BROADCASTER_USERNAME.lower()
    is_bot = user == BOT_USERNAME.lower()
    has_command = "!hehe" in msg_text
    
    if (is_broadcaster or is_bot) and has_command and DEBUG_MODE:
        HoldAndReleaseKey(G, 0.5)

async def process_queued_messages(auth):
    """
    Process chat messages from EventSub at a specified rate.
    
    Messages are queued and processed sequentially with rate limiting.
    This mode is useful for handling high message volumes without overwhelming
    the system or triggering rate limits on key press actions.
    
    Args:
        auth (TwitchAuth): Authenticated Twitch auth object
        
    Raises:
        Cancels listener task on exit
    """
    listener_task = asyncio.create_task(twitch_listener(auth))

    try:
        async for msg_data in process_messages(rate_per_second=RATE_PER_SEC):
            data = msg_data["data"]
            
            # Extract event data
            event_type = data["metadata"]["subscription_type"]
            
            if event_type != "channel.chat.message":
                continue
            
            event = data["payload"]["event"]
            broadcaster_name = event["broadcaster_user_name"]
            
            await handle_chat_message(event, broadcaster_name, rate_limited=True)
    
    finally:
        listener_task.cancel()

async def process_chat_messages(auth):
    """
    Process chat messages from EventSub in real-time without rate limiting.
    
    Messages are displayed immediately as they arrive. This mode is ideal for
    monitoring chat or situations where immediate feedback is required.
    
    Args:
        auth (TwitchAuth): Authenticated Twitch auth object
        
    Raises:
        Cancels listener task on exit
    """
    listener_task = asyncio.create_task(twitch_listener(auth))

    try:
        async for msg_data in process_messages(rate_per_second=-1):
            data = msg_data["data"]
            
            # Extract event data
            event_type = data["metadata"]["subscription_type"]
            
            if event_type != "channel.chat.message":
                continue
            
            event = data["payload"]["event"]
            broadcaster_name = event["broadcaster_user_name"]
            
            await handle_chat_message(event, broadcaster_name, rate_limited=False)
    
    finally:
        listener_task.cancel()

# ===========================
# Entry Point
# ===========================

if __name__ == "__main__":
    asyncio.run(main())