# Twitch Bot Integration

A consolidated Python bot for Twitch integration supporting real-time chat monitoring, cheer detection, keyboard input simulation, and automated channel title updates based on subscriber counts.

## Overview

This project consolidates three separate modules into a unified service architecture:
- **Authentication**: OAuth2 authentication (device flow and local redirect)
- **EventSub Listener**: Real-time WebSocket listener for Twitch events
- **Chat Processing**: Real-time or rate-limited message handling
- **Title Updates**: Automatic channel title updates with subscriber count progression

## Project Structure

```
.
├── main.py                      # Entry point and mode routing
├── twitch_service.py            # Consolidated Twitch service (authentication, API, EventSub)
├── dotenv.py                    # Custom .env file parser
├── KeyCodes.py                  # DirectX key codes and keyboard input
├── scopes.py                    # Twitch OAuth2 scopes
├── requirements.txt             # Python dependencies
├── .env                         # Configuration (create from .env.example)
└── twitch_token-*.json         # OAuth tokens (auto-generated)
```

## Installation

### Prerequisites
- Python 3.10+ ([Installation guide](https://realpython.com/installing-python/))
- Twitch application (created at https://dev.twitch.tv/console)
- Windows or Linux (Linux has limited functionality for keyboard input)

### Twitch Developer Console Setup

1. **Create a Twitch Application**:
   - Go to https://dev.twitch.tv/console/apps/create
   - Name it whatever you want
   - Set **OAuth Redirect URLs** to: `http://localhost:8090`
   - Set **Category** to: Website Integration
   - Set **Client Type** to: Confidential
   - Copy your **Client ID** and **Client Secret** (you'll need these in `.env`)

### Setup

1. **Clone or download this repository**:
   ```bash
   git clone https://github.com/ajhyperbit/Twitch-Projects.git
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file** with your configuration:
   ```bash
   # Required: Twitch Application
   TWITCH_CLIENT_ID=your_client_id
   TWITCH_CLIENT_SECRET=your_client_secret
   
   # Required: Usernames
   BROADCASTER_USERNAME=your_channel_name
   BOT_USERNAME=your_bot_username
   
   # Mode selection (title, chat, or queued)
   MODE=queued
   
   # Optional: Chat processing rate (messages per second)
   RATE_PER_SEC=1
   
   # Title Update Configuration (only for "title" mode)
   MAX_SUBS=100
   UPDATE_INTERVAL_MINUTES=1
   BASE_SUBS=10
   BASE_MULT=1.5
   LINEAR=False
   Title0="Streaming with"
   Title1="subs!"
   insert_after=0
   
   # Optional: Debug mode
   DEBUG=0
   ```

4. **Run the bot**:
   ```bash
   python main.py
   ```
   - First run will prompt you to authorize via Twitch
   - A token file (`twitch_token-{USER_ID}.json`) will be automatically created and saved
   - Token is automatically refreshed when expired, or re-authenticates if for any other reason it does not work

## Configuration

### Environment Variables

#### Required
- `TWITCH_CLIENT_ID`: Your Twitch application client ID
- `TWITCH_CLIENT_SECRET`: Your Twitch application client secret
- `BROADCASTER_USERNAME`: Twitch username of channel to monitor
- `BOT_USERNAME`: Twitch username of bot account

#### Mode Selection
- `MODE=title`: Update channel title with subscriber count
- `MODE=chat`: Display real-time chat messages
- `MODE=queued`: Display chat with rate limiting

#### Chat Processing (queued/chat modes)
- `RATE_PER_SEC`: Messages to process per second (default: 1)
- `DEBUG`: Print debug messages (0=off, 1=on)

#### Title Updates (title mode)
- `MAX_SUBS`: Maximum subscriber count before stopping updates
- `UPDATE_INTERVAL_MINUTES`: Minutes between title updates (supports floats, e.g., 0.5)
- `BASE_SUBS`: Starting subscriber count
- `BASE_MULT`: Multiplier for exponential growth (if LINEAR=False)
- `LINEAR`: Use linear growth mode (True/False)
- `Title0`: Title template prefix (with subscriber placeholder)
- `Title1`: Title template suffix (optional)
- `insert_after`: Word position to insert subscriber count

### Title Update Examples

**With suffix** (Title0 + subs + Title1):
```env
Title0=Streaming with
Title1=subs!
Title0="Streaming with"    # "Streaming with 10 subs!"
Title1="subs!"
```

**With position insertion** (words split by spaces):
```env
Title0=Live Skyrim Speedrun Challenge Stream
insert_after=2            # Insert at position 2
# Result: "Live Skyrim 10 Speedrun Challenge Stream"
```

### Growth Modes

**Linear Growth** (add fixed amount each update):
```env
LINEAR=True
BASE_SUBS=10
# 10 → 20 → 30 → 40 → ... → MAX_SUBS
```

**Exponential Growth** (multiply each update):
```env
LINEAR=False
BASE_SUBS=10
BASE_MULT=1.5
# 10 → 15 → 22 → 33 → 49 → ... → MAX_SUBS
```

## Usage

### Mode: Title Updates
Continuously updates channel title with increasing subscriber count:
```bash
MODE=title python main.py
```
- Fetches channel ID from BROADCASTER_USERNAME
- Updates title with current subscriber count
- Waits UPDATE_INTERVAL_MINUTES (supports fractional minutes like 0.5)
- Calculates next subscriber count (linear or exponential)
- Stops when MAX_SUBS reached

### Mode: Real-time Chat
Displays incoming chat messages immediately:
```bash
MODE=chat python main.py
```
- Connects to EventSub WebSocket
- Subscribes to channel.chat.message events
- Displays messages instantly (no rate limiting)
- Detects and logs cheer/bit messages
- Processes special commands for specific users

### Mode: Queued Chat
Displays chat messages with rate limiting:
```bash
MODE=queued python main.py
```
- Queues incoming messages
- Processes at RATE_PER_SEC rate (default: 1 msg/sec)
- Useful for slower display or processing

## Authentication Flow

### Device Flow (Default)
1. Bot displays Twitch URL and device code
2. You visit URL and enter device code
3. Bot polls for approval and obtains token
4. Token saved to `twitch_token-{broadcaster_id}.json`

### Local Redirect Flow
Modify `main.py` to use `method="local"`:
1. Browser opens OAuth authorization page
2. Local HTTP server receives callback
3. Token exchanged and saved automatically

## Architecture

### Core Components

**twitch_service.py** (520+ lines)
- `TwitchAuth` class: OAuth2 authentication with device flow and local redirect
- `get_app_token()`: Application credentials with token caching
- `get_channel_id()`: User lookup with ID caching
- `twitch_listener()`: EventSub WebSocket listener
- `process_messages()`: Rate-limited message yielder
- Title update functions: `calculate_subs()`, `format_title()`, `update_title()`, `update_title_loop()`

**main.py** (~130 lines)
- Module docstring: Detailed mode and configuration documentation
- `handle_chat_message()`: Unified message handler for all modes
- `process_chat_messages()`: Real-time message processing
- `process_queued_messages()`: Rate-limited message processing
- `main()`: Mode router

**Supporting Modules**
- `dotenv.py`: Custom .env parser with inline comment support
- `KeyCodes.py`: DirectX key codes and keyboard input (Windows only)
- `scopes.py`: Twitch OAuth2 scopes definition

## Key Features

### Caching Mechanisms
- **App Token Cache**: Eliminates redundant API calls for channel lookups
- **Channel ID Cache**: Persists user ID lookups in memory

### Message Handling
- **Unified Handler**: Same logic for chat and queued modes
- **Cheer Detection**: Identifies and logs bit cheers
- **Special Commands**: Bot responds to specific users (e.g., `!keyboard Q`)

### Flexible Configuration
- Float support for UPDATE_INTERVAL_MINUTES (e.g., 0.5 minutes)
- Multiple title formatting options
- Linear and exponential subscriber progression
- Inline comments in .env file support

### Debug Mode
Enable with `DEBUG=1` to see:
- WebSocket messages
- EventSub subscription payloads
- API request details
- Message queue operations

## Message Formats

### Chat Message Structure
```json
{
  "metadata": {
    "message_type": "notification",
    "subscription_type": "channel.chat.message"
  },
  "payload": {
    "event": {
      "chatter_user_id": "123456",
      "chatter_user_name": "username",
      "message_id": "msg123",
      "message": {
        "text": "hello chat!",
        "fragments": [...]
      },
      "cheer": {
        "bits": 100
      }
    }
  }
}
```

## Troubleshooting

### Token Expired
- Delete `twitch_token-*.json` file(s)
- Run bot again to re-authenticate

### Authorization Denied
- Check OAuth scopes in `scopes.py`
- Ensure Twitch application has correct redirect URI configured

### No Messages Received
- Verify BOT_USERNAME can read chat (check channel follower status)
- Check DEBUG=1 to see WebSocket connection messages
- Confirm channel.chat.message subscription succeeds

### Keyboard Input Not Working
- Runs only on Windows (Linux displays warning)
- Ensure `KeyCodes.py` functions are called from message handler

## Inline Comments in .env

The .env parser supports inline comments:
```env
BASE_MULT=2 # Exponential multiplier
DEBUG=1     # Enable debug output
```

Comments are stripped automatically using `partition("#")`.

## Development

### Adding New Modes
1. Add new mode name to `MODE` environment variable handling
2. Create new handler function in `main.py`
3. Call from `main()` function

### Adding New Message Types
1. Update `twitch_listener()` to subscribe to new event type
2. Add event handler in message processing logic
3. Update message queue to include new data

### Token Refresh
Handled automatically by `TwitchAuth.get_valid_token()`:
1. Checks token expiration
2. Attempts refresh if expired
3. Re-authenticates if refresh fails

## Dependencies

- **requests**: HTTP client for Twitch API calls
- **aiohttp**: Async HTTP client for EventSub subscriptions
- **websockets**: WebSocket protocol for EventSub listener
- **pynput**: Cross-platform keyboard input
- **python-dotenv**: Environment variable loading

See `requirements.txt` for versions.

## License

See LICENSE.txt for license information.

## References

- [Twitch EventSub Documentation](https://dev.twitch.tv/docs/eventsub)
- [Twitch OAuth Scopes](https://dev.twitch.tv/docs/authentication/scopes)
- [Twitch API Reference](https://dev.twitch.tv/docs/api/reference)
- [DirectX Key Codes](https://docs.microsoft.com/en-us/previous-versions/visualstudio/visual-studio-6.0/aa299374)

## Changelog

### v1.0 (Current)
- Consolidated three separate files into unified service
- Added app token caching and channel ID caching
- Implemented float support for UPDATE_INTERVAL_MINUTES
- Fixed .env inline comment handling
- Made chat mode fully functional
- Added comprehensive documentation

### Previous Versions
- v0.2: Separate service modules (twitch_auth.py, twitch_functions.py, title_functions.py)
- v0.1: Initial implementation
