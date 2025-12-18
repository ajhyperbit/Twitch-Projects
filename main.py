import os
from dotenv import load_dotenv
import asyncio
from twitch_functions import *
from twitch_auth import TwitchAuth
from scopes import SCOPES
from KeyCodes import *
#from chat import main_chat

load_dotenv()

# Variables
mode = os.getenv("mode").lower()
RATE_PER_SEC = int(os.getenv("RATE_PER_SEC"))
BASE_SUBS = int(os.getenv("BASE_SUBS"))
BOT_USERNAME = (os.getenv("BOT_USERNAME"))
BROADCASTER_USERNAME = (os.getenv("BROADCASTER_USERNAME"))
#For messages event sub
TWITCH_WS_URL = "wss://eventsub.wss.twitch.tv/ws"
TWITCH_API_URL = "https://api.twitch.tv/helix/eventsub/subscriptions"

BROADCASTER_ID = get_channel_id(BROADCASTER_USERNAME)
auth = TwitchAuth(scopes=SCOPES, broadcaster_id=BROADCASTER_ID)

async def main():
    auth.get_valid_token(validate=True)
    if mode == "title":
        update_title_loop(auth)
    elif mode == "chat" or mode == "bits" or mode == "message" or mode == "messages":
        asyncio.run(twitch_listener(auth))
    #asyncio.run(main_chat())
    elif mode == "queued":
        await queued_msgs(auth)
    else:
        print("Please ensure you have a valid mode. Valid modes are: title, chat, queued")


#async def queued_msgs(auth):
#    consumer_task = asyncio.create_task(process_messages(rate_per_second=RATE_PER_SEC))
#    listener_task = asyncio.create_task(twitch_listener(auth))
#    
#    await asyncio.gather(listener_task, consumer_task)


async def queued_msgs(auth):
    listener_task = asyncio.create_task(twitch_listener(auth))

    try:
        async for data in process_messages(rate_per_second=RATE_PER_SEC):
            #print("Handling:", msg)
                data = data["data"]
                #print(data)
                mtype = data["metadata"]["message_type"]

                if mtype == "notification":
                    event_type = data["metadata"]["subscription_type"]
                    event = data["payload"]["event"]
                
                    user = event["chatter_user_name"]
                    user = user.lower()
                    msg_text = event["message"]["text"]
                    broadcaster_user_name = event["broadcaster_user_name"]
                    #print(f"[Chat: {broadcaster_user_name}] {user}: {msg_text}")

                    if event_type == "channel.chat.message":
                        cheer = data["payload"]["event"]["cheer"]
                        if cheer != 'null':
                            print("NonCheer msg")
                            #print(f"[Chat: {broadcaster_user_name}] {user}: {msg_text}")
                            pass
                        else:
                            #print("Cheer msg")
                            HoldAndReleaseKey(G, 0.5)
                            #print(f"[Chat: {broadcaster_user_name}] {user}: {msg_text}")
                        if user == 'aj_hyper_bit' and '!hehe' in msg_text:
                            HoldAndReleaseKey(G, 0.5)
    finally:
        listener_task.cancel()

# Run with your auth object
# asyncio.run(main(auth))


if __name__ == "__main__":
    asyncio.run(main())