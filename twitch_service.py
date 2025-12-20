"""
Consolidated Twitch integration service.
Combines authentication, EventSub listener, and title update functionality.
"""

import os
import sys
import json
import time
import webbrowser
import threading
import requests
import aiohttp
import asyncio
import websockets
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

# ===========================
# Configuration
# ===========================

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
PORT = 8090
REDIRECT_URI = f"http://localhost:{PORT}"
DEFAULT_SCOPES = ["user:read:email"]

# Twitch API endpoints
TWITCH_WS_URL = "wss://eventsub.wss.twitch.tv/ws"
TWITCH_API_URL = "https://api.twitch.tv/helix/eventsub/subscriptions"

# User configuration
BROADCASTER_USERNAME = os.getenv("BROADCASTER_USERNAME")
BOT_USERNAME = os.getenv("BOT_USERNAME")
DEBUG = int(os.getenv("DEBUG", 0))

# Title update configuration
MAX_SUBS = int(os.getenv("MAX_SUBS", 0))
UPDATE_INTERVAL_MINUTES = float(os.getenv("UPDATE_INTERVAL_MINUTES", 60))
BASE_SUBS = int(os.getenv("BASE_SUBS", 0))
BASE_MULT = float(os.getenv("BASE_MULT", 1.0))
LINEAR = os.getenv("LINEAR", "False").lower() == "true"
TITLE_TEMPLATE = os.getenv("title") or os.getenv("Title0") or ""
TITLE_SUFFIX = os.getenv("Title1", "")
INSERT_AFTER = int(os.getenv("insert_after", 0))

# Message queue for async processing
message_queue = asyncio.Queue()

# Cache for channel IDs and app tokens to avoid redundant API calls
_channel_id_cache = {}
_app_token_cache = {"token": None, "expires_at": None}


# ===========================
# Authentication
# ===========================

class TwitchAuth:
    """
    Handles OAuth2 authentication with Twitch.
    
    Supports multiple authentication methods:
    - Device Code Flow: User visits Twitch website to authorize (no web server needed)
    - Local Redirect Flow: Web server receives OAuth callback (local development)
    - Token Refresh: Automatically refreshes expired tokens
    - Token Validation: Verifies token scope permissions
    
    Tokens are persisted to JSON files named after broadcaster_id for reuse.
    
    Attributes:
        client_id (str): Twitch application client ID
        client_secret (str): Twitch application client secret
        scopes (list): OAuth2 scopes required (e.g., ['user:read:email'])
        broadcaster_id (str): Twitch user ID (used for token file naming)
        token_file (str): Path to token JSON file
    
    Example:
        auth = TwitchAuth(broadcaster_id="123456")
        token = auth.get_valid_token(method="device")
    """

    def __init__(self, scopes=None, broadcaster_id=None, bot_id=None):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.scopes = scopes if scopes is not None else DEFAULT_SCOPES
        self.broadcaster_id = broadcaster_id
        self.bot_id = bot_id
        self.token_file = None

        if not self.client_id or not self.client_secret:
            raise RuntimeError("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET")

        if self.broadcaster_id:
            self.token_file = f"twitch_token-{self.broadcaster_id}.json"

    def save_token(self, data):
        """
        Save token to file with calculated expiration time.
        
        Adds expires_at field with UTC timestamp and writes to token_file.
        Used after successful authentication to persist tokens for reuse.
        
        Args:
            data (dict): Token data from Twitch (must include expires_in)
        """
        data["expires_at"] = (
            datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
        ).isoformat()
        with open(self.token_file, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Tokens saved to {self.token_file}")

    def load_token(self):
        """
        Load token from file if it exists.
        
        Returns:
            dict: Token data from file or None if file not found
        """
        if not os.path.exists(self.token_file):
            return None
        with open(self.token_file, "r") as f:
            return json.load(f)

    def _request_device_code(self):
        """
        Request a device code for device flow authentication.
        
        Used by authenticate_device() to initiate the flow.
        Returns codes that user enters on Twitch website.
        
        Returns:
            dict: Contains device_code, user_code, verification_uri, interval
        """
        url = "https://id.twitch.tv/oauth2/device"
        payload = {"client_id": self.client_id, "scopes": " ".join(self.scopes)}
        r = requests.post(url, data=payload)
        r.raise_for_status()
        return r.json()

    def _poll_for_token(self, device_code, interval):
        """
        Poll Twitch for token completion in device flow.
        
        Repeatedly checks if user has completed authorization. Handles:
        - authorization_pending: User hasn't authorized yet (keep polling)
        - slow_down: Rate limit hit (increase interval)
        - 200 response: Authorization complete (return token)
        
        Args:
            device_code (str): Device code from _request_device_code()
            interval (int): Seconds to wait between polls (increases on slow_down)
            
        Returns:
            dict: Token data with access_token and refresh_token
            
        Raises:
            Exception: If unexpected error response from Twitch
        """
        url = "https://id.twitch.tv/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        while True:
            time.sleep(interval)
            r = requests.post(url, data=payload)

            if r.status_code == 200:
                print("Authorization complete!")
                return r.json()

            data = r.json()
            msg = data.get("error") or data.get("message")

            if msg == "authorization_pending":
                print("Waiting for user authorization...")
                continue
            if msg == "slow_down":
                interval += 5
                print("Slowing down polling...")
                continue

            raise Exception(f"Token polling failed: {data}")

    def authenticate_device(self):
        """
        Authenticate using device code flow.
        
        User-friendly authentication for CLI applications:
        1. Requests device code from Twitch
        2. Displays verification URL and code
        3. Polls for token completion as user authorizes
        4. Saves token to file
        
        Returns:
            dict: Token data with access_token and refresh_token
        """
        device_data = self._request_device_code()
        print("=== DEVICE AUTHORIZATION ===")
        print(f"Go to: {device_data['verification_uri']}")
        print(f"Enter the code: {device_data['user_code']}")
        print("============================")

        token_data = self._poll_for_token(
            device_code=device_data["device_code"], interval=device_data["interval"]
        )
        self.save_token(token_data)
        return token_data

    def authenticate_local(self):
        """
        Authenticate using local redirect flow.
        
        Opens browser-based OAuth flow with local callback server:
        1. Opens Twitch OAuth URL in default browser
        2. Starts local HTTP server to receive redirect
        3. Exchanges authorization code for token
        4. Saves token to file
        
        Returns:
            dict: Token data from file
        """
        scope_str = "+".join(self.scopes)
        auth_url = (
            f"https://id.twitch.tv/oauth2/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&response_type=code"
            f"&scope={scope_str}"
        )

        print("Opening Twitch OAuth URL in browser...")
        webbrowser.open(auth_url)

        server = HTTPServer(("localhost", PORT), self._make_local_handler())
        print(f"Waiting for Twitch redirect at {REDIRECT_URI}...")
        server.serve_forever()

        return self.load_token()

    def _make_local_handler(self):
        """
        Create custom HTTP request handler for OAuth callback.
        
        Handles Twitch redirect with authorization code, exchanges for token.
        Used by authenticate_local() to process OAuth callback.
        
        Returns:
            class: HTTP request handler with do_GET method
        """
        parent = self

        class OAuthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)

                if "code" not in params:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing ?code= in callback.")
                    return

                code = params["code"][0]
                print(f"Received authorization code: {code}")

                token_resp = requests.post(
                    "https://id.twitch.tv/oauth2/token",
                    params={
                        "client_id": parent.client_id,
                        "client_secret": parent.client_secret,
                        "code": code,
                        "grant_type": "authorization_code",
                        "redirect_uri": REDIRECT_URI,
                    },
                )

                if token_resp.status_code != 200:
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b"Failed to exchange code for token.")
                    print("Token exchange failed:", token_resp.text)
                    return

                token_data = token_resp.json()
                parent.save_token(token_data)

                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Twitch token saved successfully! You can close this window.")
                threading.Thread(target=self.server.shutdown).start()

            def log_message(self, format, *args):
                """Suppress default logging."""
                pass

        return OAuthHandler

    def refresh_token(self, refresh_token):
        """
        Refresh an expired access token using refresh token.
        
        Used by get_valid_token() when token nears or passes expiration.
        
        Args:
            refresh_token (str): Refresh token from previous authentication
            
        Returns:
            dict: New token data with fresh access_token
            
        Raises:
            HTTPError: If refresh fails
        """
        url = "https://id.twitch.tv/oauth2/token"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        r = requests.post(url, data=payload)
        r.raise_for_status()
        return r.json()

    def get_valid_token(self, method="device", validate=False):
        """
        Get a valid access token, refreshing or re-authenticating if needed.
        
        Smart token management:
        1. Check if saved token exists and is still valid
        2. If expired, attempt refresh with refresh_token
        3. If no refresh token or refresh fails, re-authenticate
        4. Optionally validate token scopes against requirements
        
        Args:
            method (str): Authentication method if re-auth needed ("device" or "local")
            validate (bool): Whether to validate token scopes with Twitch
            
        Returns:
            str: Valid access token
            
        Raises:
            ValueError: If authentication method is invalid
        """
        token_data = self.load_token()
        now = datetime.now(timezone.utc)

        if token_data and "access_token" in token_data:
            expires_at = datetime.fromisoformat(token_data["expires_at"])

            if now < expires_at:
                access_token = token_data["access_token"]

                if validate:
                    resp = requests.get(
                        "https://id.twitch.tv/oauth2/validate",
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    if resp.status_code != 200:
                        print("Token invalid according to Twitch:", resp.text)
                    else:
                        data = resp.json()
                        token_scopes = data.get("scopes", [])
                        missing_scopes = [s for s in self.scopes if s not in token_scopes]
                        if missing_scopes:
                            print("Token missing required scopes:", missing_scopes)
                            return self.reauthenticate(method)
                        else:
                            print("Token has all required scopes.")

                return access_token

            print("Token expired locally, attempting refresh...")
            if "refresh_token" in token_data:
                try:
                    token_data = self.refresh_token(token_data["refresh_token"])
                    self.save_token(token_data)
                    return token_data["access_token"]
                except Exception as e:
                    print("Refresh failed:", e)

        print("Starting full re-authentication...")
        return self.reauthenticate(method)

    def reauthenticate(self, method="device"):
        """
        Perform full re-authentication with chosen method.
        
        Used when token is missing, invalid, or refresh fails.
        
        Args:
            method (str): "device" for device flow, "local" for browser flow
            
        Returns:
            str: New access token
            
        Raises:
            ValueError: If method not recognized
        """
        if method == "device":
            token_data = self.authenticate_device()
        elif method == "local":
            token_data = self.authenticate_local()
        else:
            raise ValueError(f"Unknown authentication method: {method}")
        return token_data["access_token"]

    def get_headers(self, json_body=False, method="device", validate=False):
        """
        Get HTTP headers with valid access token for API requests.
        
        Prepares Authorization header with current valid token.
        Optionally adds Content-Type for JSON requests.
        
        Args:
            json_body (bool): Whether to add Content-Type: application/json
            method (str): Auth method if re-authentication needed
            validate (bool): Whether to validate token scopes
            
        Returns:
            dict: Headers ready for Twitch API request
            
        Example:
            headers = auth.get_headers(json_body=True)
            requests.post(url, headers=headers, json=data)
        """
        access_token = self.get_valid_token(method=method, validate=validate)
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {access_token}",
        }
        if json_body:
            headers["Content-Type"] = "application/json"
        return headers


# ===========================
# Twitch API Utilities
# ===========================

def get_app_token(client_id: str, client_secret: str) -> str:
    """
    Get an app access token using OAuth2 client credentials flow.
    
    Implements caching to minimize API calls. Returns cached token if still valid.
    Otherwise requests new token from Twitch and caches with expiration time.
    
    Args:
        client_id (str): Twitch application client ID
        client_secret (str): Twitch application client secret
        
    Returns:
        str: Valid access token for API requests
        
    Raises:
        HTTPError: If token request fails
    """
    # Check if cached token is still valid
    if _app_token_cache["token"] and _app_token_cache["expires_at"]:
        if datetime.now(timezone.utc) < _app_token_cache["expires_at"]:
            return _app_token_cache["token"]
    
    url = "https://id.twitch.tv/oauth2/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    r = requests.post(url, data=payload)
    r.raise_for_status()
    token_data = r.json()
    
    # Cache the token with expiration time
    _app_token_cache["token"] = token_data["access_token"]
    _app_token_cache["expires_at"] = (
        datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])
    )
    return token_data["access_token"]


def get_channel_id(username: str) -> str:
    """
    Fetch the Twitch channel ID for a given username.
    
    Caches results to minimize API calls. Returns cached ID if previously looked up.
    Otherwise calls Twitch API to retrieve user ID and caches for future calls.
    
    Args:
        username (str): Twitch username to look up
        
    Returns:
        str: Twitch user ID (channel ID)
        
    Raises:
        ValueError: If username not found on Twitch
        HTTPError: If API request fails
    """
    if username in _channel_id_cache:
        return _channel_id_cache[username]

    app_token = get_app_token(CLIENT_ID, CLIENT_SECRET)
    headers = {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {app_token}"
    }
    params = {"login": username}
    response = requests.get("https://api.twitch.tv/helix/users", headers=headers, params=params)
    response.raise_for_status()
    data = response.json()
    if not data["data"]:
        raise ValueError(f"No user found with username '{username}'")
    
    channel_id = data["data"][0]["id"]
    _channel_id_cache[username] = channel_id
    return channel_id


# ===========================
# EventSub Subscriptions
# ===========================

async def subscribe_event(auth: TwitchAuth, session_id, event_type, condition, version=1):
    """
    Subscribe to a Twitch EventSub event type via WebSocket.
    
    Registers a listener for specific Twitch events (e.g., channel.chat.message)
    through the EventSub WebSocket. Requires active WebSocket session.
    
    Args:
        auth (TwitchAuth): Authenticated TwitchAuth object for headers
        session_id (str): Active EventSub WebSocket session ID
        event_type (str): EventSub event type (e.g., 'channel.chat.message')
        condition (dict): Event condition (e.g., broadcaster_user_id, user_id)
        version (int): EventSub schema version (default: 1)
        
    Raises:
        HTTPError: If subscription fails
        SystemExit: If authorization fails (403 status code)
        
    Example:
        await subscribe_event(auth, "session123", "channel.chat.message",
                            {"broadcaster_user_id": "123", "user_id": "456"})
    """
    payload = {
        "type": event_type,
        "version": version,
        "condition": condition,
        "transport": {"method": "websocket", "session_id": session_id}
    }
    headers = auth.get_headers(json_body=True)
    
    if DEBUG:
        print("\n=== EventSub Debug ===")
        print("Payload:", json.dumps(payload, indent=2))
        print("Headers:", json.dumps(headers, indent=2))
        print("Sending Request...\n")

    async with aiohttp.ClientSession() as session:
        async with session.post(TWITCH_API_URL, headers=headers, json=payload) as resp:
            try:
                data = await resp.json()
            except Exception:
                text = await resp.text()
                if DEBUG:
                    print("Non-JSON Response:", text)
                return
            
            if DEBUG:
                print("Status:", resp.status)
                print("Response:", json.dumps(data, indent=2))

            if resp.status == 403:
                print(f"\nAuthorization failed for subscription {event_type} v{version}")
                sys.exit(1)

            return data


# ===========================
# EventSub Listener
# ===========================

async def twitch_listener(auth: TwitchAuth):
    """
    Listen to Twitch EventSub WebSocket for incoming events.
    
    Connects to Twitch's EventSub WebSocket endpoint and processes incoming messages:
    - Establishes session on welcome message
    - Subscribes to channel.chat.message events
    - Queues chat messages for processing
    - Handles session reconnects
    
    Args:
        auth (TwitchAuth): Authenticated TwitchAuth object for API requests
        
    Raises:
        ConnectionError: If WebSocket connection fails
        Exception: From subscribe_event() if subscription fails
        
    Note:
        - Runs continuously until connection closes or reconnect is needed
        - Uses asyncio queue (message_queue) to pass events to handlers
        - Requires BROADCASTER_USERNAME and BOT_USERNAME in environment
    """
    async with websockets.connect(TWITCH_WS_URL) as ws:
        async for msg in ws:
            if DEBUG:
                print(f"[DEBUG] Received WebSocket message")
            data = json.loads(msg)
            mtype = data["metadata"]["message_type"]

            if mtype == "session_welcome":
                session_id = data["payload"]["session"]["id"]
                print(f"Connected with session {session_id}")

                broadcaster_id = get_channel_id(BROADCASTER_USERNAME)
                user_id = get_channel_id(BOT_USERNAME)
                
                try:
                    await subscribe_event(
                        auth,
                        session_id,
                        "channel.chat.message",
                        {
                            "broadcaster_user_id": broadcaster_id,
                            "user_id": user_id
                        }
                    )
                except Exception as e:
                    print(f"Subscription error: {e}")

            elif mtype == "notification":
                event_type = data["metadata"]["subscription_type"]
                event = data["payload"]["event"]
                
                if DEBUG:
                    print(f"[DEBUG] Received notification: {event_type}")

                if event_type == "channel.chat.message":
                    if DEBUG:
                        print(f"[DEBUG] Putting chat message in queue")
                    await message_queue.put({'data': data})

            elif mtype == "session_reconnect":
                new_url = data["payload"]["session"]["reconnect_url"]
                print("Reconnect to:", new_url)
                return await twitch_listener(auth)


async def process_messages(rate_per_second=1):
    """
    Async generator that yields messages from queue at specified rate.
    
    Pulls messages from the message_queue and yields them at a controlled rate.
    Supports two modes:
    - rate_per_second=-1: Unlimited (yields immediately)
    - rate_per_second>0: Rate-limited (adds delay between messages)
    
    Args:
        rate_per_second (float): Messages per second (-1 for unlimited)
        
    Yields:
        dict: Message data from queue
        
    Example:
        async for msg in process_messages(rate_per_second=2):
            print(msg)  # Process 2 messages per second
    """
    if rate_per_second == -1:
        while True:
            msg = await message_queue.get()
            yield msg
    else:
        interval = 1 / rate_per_second
        while True:
            msg = await message_queue.get()
            yield msg
            await asyncio.sleep(interval)


# ===========================
# Title Update Functions
# ===========================

def calculate_subs(current_subs: int) -> int:
    """
    Calculate next subscriber count based on configuration.
    
    Supports two growth models configured via environment variables:
    - LINEAR mode: Adds BASE_SUBS each iteration (linear growth)
    - Exponential mode: Multiplies by BASE_MULT each iteration
    
    Args:
        current_subs (int): Current subscriber count
        
    Returns:
        int: Next subscriber count
        
    Example:
        # LINEAR=True, BASE_SUBS=10: 10 -> 20 -> 30 -> 40...
        # LINEAR=False, BASE_MULT=1.5: 10 -> 15 -> 22 -> 33...
    """
    if current_subs is None or current_subs == 0:
        return BASE_SUBS

    if LINEAR:
        return current_subs + BASE_SUBS
    else:
        return int(current_subs * BASE_MULT)


def format_title(subs: int) -> str:
    """
    Format the stream title with subscriber count.
    
    Supports two formatting modes:
    - With TITLE_SUFFIX: "Title0 {subs} Title1"
    - Without: Insert subs at position (INSERT_AFTER) in TITLE_TEMPLATE
    
    Args:
        subs (int): Subscriber count to include
        
    Returns:
        str: Formatted stream title
        
    Example:
        # TITLE_TEMPLATE="Streaming", TITLE_SUFFIX="subs!", subs=100
        # Result: "Streaming 100 subs!"
    """
    if TITLE_SUFFIX:
        # Format: "Title0 {subs} Title1"
        return f"{TITLE_TEMPLATE} {subs} {TITLE_SUFFIX}"
    else:
        # Format: Insert subs into template at position
        words = TITLE_TEMPLATE.split()
        words.insert(INSERT_AFTER, str(subs))
        return " ".join(words)


def update_title(auth: TwitchAuth, channel_id: str, new_title: str):
    """
    Update the channel title using Twitch API.
    
    Makes authenticated PATCH request to Twitch to update the channel's title.
    Requires user:manage:broadcast scope from OAuth authentication.
    
    Args:
        auth (TwitchAuth): Authenticated TwitchAuth object for API headers
        channel_id (str): Twitch channel ID to update
        new_title (str): New title text
        
    Returns:
        None
        
    Prints status message on success or error with HTTP status code
    """
    headers = auth.get_headers()
    data = {"title": new_title}

    response = requests.patch(
        f"https://api.twitch.tv/helix/channels?broadcaster_id={channel_id}",
        headers=headers,
        json=data
    )

    if response.status_code == 204:
        print(f"Title updated successfully: {new_title}")
    else:
        print(f"Failed to update title ({response.status_code}): {response.text}")


def update_title_loop(auth: TwitchAuth):
    """
    Continuously update channel title based on subscriber count.
    
    Main title update loop: fetches channel ID, then repeatedly updates the title
    with increasing subscriber counts. Exits when MAX_SUBS is reached.
    
    Process:
    1. Look up channel ID from BROADCASTER_USERNAME
    2. Initialize subscriber count to BASE_SUBS
    3. Loop:
       - Format title with current subscriber count
       - Update channel title via API
       - Wait for UPDATE_INTERVAL_MINUTES (supports fractional minutes)
       - Calculate next subscriber count using calculate_subs()
       - Exit if subs >= MAX_SUBS
    
    Args:
        auth (TwitchAuth): Authenticated TwitchAuth object for API updates
        
    Returns:
        None (returns when MAX_SUBS is reached)
        
    Requires Environment Variables:
        - BROADCASTER_USERNAME: Channel to update
        - MAX_SUBS: Maximum subscriber count before stopping
        - UPDATE_INTERVAL_MINUTES: Float minutes between updates
        - BASE_SUBS: Starting subscriber count
        - BASE_MULT or LINEAR: Growth configuration
    """
    print("Fetching channel ID...")
    channel_id = get_channel_id(BROADCASTER_USERNAME)
    print(f"Channel ID for '{BROADCASTER_USERNAME}': {channel_id}")

    subs = BASE_SUBS

    while True:
        print(f"Updating title with {subs} subs...")
        new_title = format_title(subs)
        update_title(auth, channel_id, new_title)
        # Convert minutes to seconds (handles both integers and fractional minutes)
        sleep_seconds = UPDATE_INTERVAL_MINUTES * 60
        print(f"Waiting {UPDATE_INTERVAL_MINUTES} minutes ({sleep_seconds} seconds) before next update...")
        time.sleep(sleep_seconds)
        
        subs = calculate_subs(subs)
        
        if subs >= MAX_SUBS:
            print(f"Reached maximum subscriber count ({MAX_SUBS}). Stopping updates.")
            return
