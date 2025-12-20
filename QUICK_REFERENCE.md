# Quick Reference Guide

Fast lookup guide for common tasks and configurations.

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python main.py
```

## Environment Variables Quick Reference

### Required
| Variable | Example | Purpose |
|----------|---------|---------|
| `TWITCH_CLIENT_ID` | `abc123xyz` | Twitch app ID |
| `TWITCH_CLIENT_SECRET` | `secret123` | Twitch app secret |
| `BROADCASTER_USERNAME` | `your_channel` | Channel to monitor |
| `BOT_USERNAME` | `your_bot` | Bot account name |

### Mode Selection
| Value | Behavior | Use Case |
|-------|----------|----------|
| `title` | Updates channel title with sub count | Automated title updates |
| `chat` | Shows messages in real-time | Chat monitoring |
| `queued` | Shows messages at rate limit | Controlled processing |

### Title Update Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_SUBS` | 0 | Stop updating at this count |
| `UPDATE_INTERVAL_MINUTES` | 60 | Minutes between updates (supports floats) |
| `BASE_SUBS` | 0 | Starting subscriber count |
| `BASE_MULT` | 1.0 | Multiplier (exponential mode) |
| `LINEAR` | False | True for +BASE_SUBS each update |
| `Title0` | "" | Title prefix or template |
| `Title1` | "" | Title suffix |
| `insert_after` | 0 | Word position to insert count |

### Optional
| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUG` | 0 | Enable debug output (0 or 1) |
| `RATE_PER_SEC` | 1 | Messages/sec for queued mode |
| `WEBSOCKET_HOST` | localhost | OBS WebSocket host |
| `WEBSOCKET_PORT` | 4444 | OBS WebSocket port |
| `WEBSOCKET_PASSWORD` | "" | OBS WebSocket password |

## Mode Comparison

```
┌─────────┬──────────────┬─────────────┬──────────────┐
│ Feature │ Chat Mode    │ Queued Mode │ Title Mode   │
├─────────┼──────────────┼─────────────┼──────────────┤
│ Speed   │ Immediate    │ Rate-limited│ Interval-based│
│ Messages│ Real-time    │ Queued      │ Title only   │
│ Use     │ Monitoring   │ Processing  │ Auto-update  │
│ Rate    │ Unlimited    │ RATE_PER_SEC│ UPDATE_INTER │
└─────────┴──────────────┴─────────────┴──────────────┘
```

## Common .env Configurations

### Chat Monitoring (Real-time)
```env
MODE=chat
DEBUG=1
```

### Chat Processing (1 msg/sec)
```env
MODE=queued
RATE_PER_SEC=1
```

### Slow Chat Processing (1 msg/5 sec)
```env
MODE=queued
RATE_PER_SEC=0.2
```

### Title Updates (Linear Growth)
```env
MODE=title
LINEAR=True
BASE_SUBS=10
MAX_SUBS=100
UPDATE_INTERVAL_MINUTES=1
Title0="Streaming with"
Title1="subs!"
```

### Title Updates (Exponential Growth)
```env
MODE=title
LINEAR=False
BASE_SUBS=10
BASE_MULT=1.5
MAX_SUBS=100
UPDATE_INTERVAL_MINUTES=0.5
Title0="Stream:"
Title1="Subs"
```

### Title Updates (Position Insertion)
```env
MODE=title
Title0="Skyrim Speedrun Challenge Stream"
insert_after=2
# Result: "Skyrim Speedrun 10 Challenge Stream"
```

## Authentication Methods

### Device Flow (Default - Recommended)
```
1. Bot displays URL and code
2. You visit URL and enter code
3. Token saved automatically
```

### Local Redirect Flow
Modify main.py:
```python
token = auth.get_valid_token(method="local")
```
Then:
```
1. Browser opens OAuth page
2. Local server captures redirect
3. Token saved automatically
```

## Troubleshooting Checklist

### No messages received
- [ ] `DEBUG=1` to check WebSocket connection
- [ ] Verify BOT_USERNAME follows the broadcaster's channel
- [ ] Check scopes in scopes.py are correct
- [ ] Delete and re-authenticate (remove twitch_token-*.json)

### Title not updating
- [ ] Check BROADCASTER_USERNAME is correct
- [ ] Verify channel:manage:broadcast scope is enabled
- [ ] Check MAX_SUBS > current subtitle count
- [ ] Look for API errors in DEBUG output

### Authentication fails
- [ ] Verify CLIENT_ID and CLIENT_SECRET
- [ ] Check .env inline comments (use # after value)
- [ ] Ensure all required variables are set
- [ ] Delete twitch_token-*.json and retry

### Keyboard input not working
- [ ] Only works on Windows (check OS)
- [ ] Try running as administrator
- [ ] Verify target application is in focus

## File Locations

```
twitch_token-{USER_ID}.json    <- Auto-generated tokens
.env                            <- Your configuration
README.md                       <- Full documentation
DOCUMENTATION.md               <- Documentation overview
```

## Python Imports Reference

### From twitch_service
```python
from twitch_service import (
    TwitchAuth,              # OAuth2 authentication
    get_app_token,          # App credentials
    get_channel_id,         # Username to ID lookup
    twitch_listener,        # EventSub WebSocket
    process_messages,       # Message rate limiter
    update_title_loop,      # Title update automation
)
```

### From other modules
```python
from main import handle_chat_message    # Unified message handler
from KeyCodes import HoldAndReleaseKey # Keyboard simulation
from dotenv import load_dotenv         # Env file loading
from scopes import SCOPES              # OAuth scopes
```

## Command Examples

### Check configuration
```bash
grep "^[^#]" .env | head -10
```

### View debug output
```bash
DEBUG=1 python main.py
```

### Test imports
```bash
python -c "from twitch_service import TwitchAuth; print('OK')"
```

### Get help on function
```bash
python -c "from twitch_service import get_app_token; help(get_app_token)"
```

## Rate Limiting Reference

```
┌──────────────┬─────────────────────┐
│ RATE_PER_SEC │ Messages Per Minute  │
├──────────────┼─────────────────────┤
│ 0.1          │ 6 (one per 10 sec)  │
│ 0.2          │ 12 (one per 5 sec)  │
│ 0.5          │ 30 (one per 2 sec)  │
│ 1            │ 60 (one per second) │
│ 2            │ 120 (two per sec)   │
│ 5            │ 300 (five per sec)  │
│ -1           │ Unlimited           │
└──────────────┴─────────────────────┘
```

## Time Interval Reference

```
┌──────────────────────────┬─────────────┐
│ UPDATE_INTERVAL_MINUTES  │ Actual Time │
├──────────────────────────┼─────────────┤
│ 0.1                      │ 6 seconds   │
│ 0.25                     │ 15 seconds  │
│ 0.5                      │ 30 seconds  │
│ 1                        │ 1 minute    │
│ 2                        │ 2 minutes   │
│ 60                       │ 1 hour      │
│ 1440                     │ 24 hours    │
└──────────────────────────┴─────────────┘
```

## Debugging Workflow

1. Enable DEBUG mode
   ```bash
   DEBUG=1 python main.py
   ```

2. Watch output for:
   - `Connected with session {id}` - WebSocket connected
   - `[DEBUG] Received notification` - Message received
   - API errors or connection issues

3. Check specific components
   ```bash
   # Test authentication
   python -c "from twitch_service import TwitchAuth; auth = TwitchAuth(broadcaster_id='123'); print(auth.get_valid_token())"
   
   # Test channel ID lookup
   python -c "from twitch_service import get_channel_id; print(get_channel_id('your_username'))"
   ```

4. Check token validity
   - Look in `twitch_token-*.json` for expiration time
   - Compare to current time
   - Delete if expired to force re-auth

## Performance Tips

- **Reduce API calls**: Use caching (done by default)
- **Optimize message rate**: Set `RATE_PER_SEC` appropriately
- **Minimize debug output**: Set `DEBUG=0` in production
- **Token efficiency**: App tokens cached for 5 hours
- **Channel ID caching**: Persists in memory during run

## Security Notes

- Store CLIENT_SECRET securely (never commit to git)
- Use .env.example as template, don't commit .env
- Tokens auto-cleanup at expiration
- Local callback server runs on localhost only
- Use strong WebSocket passwords for OBS

## Useful Links

- [Twitch Developer](https://dev.twitch.tv)
- [EventSub Documentation](https://dev.twitch.tv/docs/eventsub)
- [OAuth Scopes](https://dev.twitch.tv/docs/authentication/scopes)
- [Helix API Reference](https://dev.twitch.tv/docs/api/reference)

## Getting Help

1. Check README.md for full documentation
2. Check DOCUMENTATION.md for detailed docs
3. Read function docstrings: `help(function_name)`
4. Enable DEBUG mode for detailed output
5. Check your .env configuration
