import os
import asyncio
import logging
import random

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("VampireUserbot")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]
MONGO_DB_URI = os.environ["MONGO_DB_URI"]

mongo = AsyncIOMotorClient(MONGO_DB_URI)
db = mongo["vampire_userbot_db"]
opted_in = db["tag_optin"]

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH,
)

HELP = (
    "🦇 ᴠᴀᴍᴘɪʀᴇ ᴜsᴇʀʙᴏᴛ\n\n"
    ".help — ᴄᴏᴍᴍᴀɴᴅ ʜᴇʟᴘ\n"
    ".optin — ᴛᴀɢɢɪɴɢ ᴏᴘᴛ-ɪɴ\n"
    ".optout — ᴛᴀɢɢɪɴɢ ᴏᴘᴛ-ᴏᴜᴛ\n"
    ".tagall <message> — ᴜᴘ ᴛᴏ 5 ᴏᴘᴛᴇᴅ-ɪɴ ᴍᴇᴍʙᴇʀs\n"
    ".randomtag — ʀᴀɴᴅᴏᴍ ᴏᴘᴛᴇᴅ-ɪɴ ᴍᴇᴍʙᴇʀ\n\n"
    "ᴛᴀɢɢɪɴɢ ɪs ʟɪᴍɪᴛᴇᴅ ᴛᴏ ᴍᴇᴍʙᴇʀs ᴡʜᴏ "
    "ᴇxᴘʟɪᴄɪᴛʟʏ ᴏᴘᴛ ɪɴ."
)


def mention(user, label=None):
    name = label or user.first_name or "Member"
    return f"[{name}](tg://user?id={user.id})"


async def group_only(event):
    return bool(event.is_group or event.is_channel)


@client.on(events.NewMessage(pattern=r"^\.help$"))
async def help_handler(event):
    await event.reply(HELP, parse_mode="md")


@client.on(events.NewMessage(pattern=r"^\.optin$"))
async def optin_handler(event):
    if not await group_only(event):
        await event.reply("ᴜsᴇ ᴛʜɪs ɪɴ ᴀ ɢʀᴏᴜᴘ.")
        return

    sender = await event.get_sender()
    await opted_in.update_one(
        {"chat_id": event.chat_id, "user_id": sender.id},
        {"$set": {"enabled": True}},
        upsert=True,
    )
    await event.reply("✅ ʏᴏᴜ ᴏᴘᴛᴇᴅ ɪɴ ᴛᴏ ɢʀᴏᴜᴘ ᴛᴀɢɢɪɴɢ.")


@client.on(events.NewMessage(pattern=r"^\.optout$"))
async def optout_handler(event):
    sender = await event.get_sender()
    await opted_in.delete_one(
        {"chat_id": event.chat_id, "user_id": sender.id}
    )
    await event.reply("✅ ʏᴏᴜ ᴏᴘᴛᴇᴅ ᴏᴜᴛ.")


@client.on(events.NewMessage(pattern=r"^\.tagall(?:\s+(.+))?$"))
async def tagall_handler(event):
    if not await group_only(event):
        await event.reply("ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
        return

    # Only group administrators may initiate tagging.
    sender = await event.get_sender()
    try:
        permissions = await client.get_permissions(event.chat_id, sender)
        if not (permissions.is_admin or permissions.is_creator):
            await event.reply("❌ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴs ᴏɴʟʏ.")
            return
    except Exception:
        await event.reply("ᴄᴏᴜʟᴅ ɴᴏᴛ ᴠᴇʀɪғʏ ᴀᴅᴍɪɴ ᴘᴇʀᴍɪssɪᴏɴs.")
        return

    custom_message = event.pattern_match.group(1) or "Hello!"

    records = await opted_in.find({
        "chat_id": event.chat_id,
        "enabled": True,
    }).to_list(length=1000)

    # One invocation tags at most five consenting members.
    chosen = random.sample(records, min(5, len(records)))

    if not chosen:
        await event.reply(
            "ɴᴏ ᴍᴇᴍʙᴇʀs ʜᴀᴠᴇ ᴏᴘᴛᴇᴅ ɪɴ ʏᴇᴛ. "
            "ᴍᴇᴍʙᴇʀs ᴄᴀɴ ᴜsᴇ .optin."
        )
        return

    tags = []
    for record in chosen:
        try:
            user = await client.get_entity(record["user_id"])
            tags.append(mention(user))
        except Exception:
            continue

    if tags:
        await event.reply(
            custom_message + "\n\n" + " ".join(tags),
            parse_mode="md",
        )


@client.on(events.NewMessage(pattern=r"^\.randomtag$"))
async def randomtag_handler(event):
    if not await group_only(event):
        await event.reply("ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
        return

    records = await opted_in.find({
        "chat_id": event.chat_id,
        "enabled": True,
    }).to_list(length=1000)

    if not records:
        await event.reply("ɴᴏ ᴍᴇᴍʙᴇʀs ʜᴀᴠᴇ ᴏᴘᴛᴇᴅ ɪɴ.")
        return

    record = random.choice(records)
    try:
        user = await client.get_entity(record["user_id"])
        await event.reply(
            "🎯 " + mention(user),
            parse_mode="md",
        )
    except Exception:
        await event.reply("ᴄᴏᴜʟᴅ ɴᴏᴛ ᴛᴀɢ ᴛʜɪs ᴍᴇᴍʙᴇʀ.")


async def main():
    await client.start()
    me = await client.get_me()
    log.info("Userbot started: %s (%s)", me.first_name, me.id)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
