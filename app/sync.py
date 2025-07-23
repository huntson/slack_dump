import os
import logging
from datetime import datetime, timezone
from tenacity import retry, wait_random_exponential, stop_after_attempt
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from sqlalchemy.exc import IntegrityError

from .models import db, Channel, User, Message, Reaction

log = logging.getLogger("sync")

def env_bool(name, default=False):
    return str(os.getenv(name, str(default))).lower() in ("1", "true", "yes", "y")

@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(5))
def safe_call(func, **kwargs):
    return func(**kwargs)

def upsert(model_obj):
    try:
        db.session.merge(model_obj)
    except IntegrityError:
        db.session.rollback()
        db.session.merge(model_obj)

def fetch_users(client, progress=None):
    cursor = None
    total = 0
    while True:
        resp = safe_call(client.users_list, cursor=cursor, limit=200)
        for u in resp["members"]:
            user = User(
                id=u.get("id"),
                name=u.get("name"),
                real_name=u.get("real_name"),
                tz=u.get("tz"),
            )
            upsert(user)
            total += 1
        db.session.commit()
        if progress:
            progress["users"] = total
        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break

def fetch_channel_map(client, types):
    mapping = {}
    cursor = None
    while True:
        resp = safe_call(client.conversations_list, cursor=cursor, limit=200, types=types)
        for c in resp["channels"]:
            mapping[c["id"]] = c["name"]
        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break
    return mapping

def store_channel(info):
    ch = Channel(
        id=info["id"],
        name=info.get("name"),
        is_private=info.get("is_private", False),
        created=datetime.fromtimestamp(info.get("created", 0), tz=timezone.utc) if info.get("created") else None,
    )
    upsert(ch)

def store_message(m, channel_id):
    msg = Message(
        ts=m["ts"],
        channel_id=channel_id,
        user_id=m.get("user"),
        text=m.get("text"),
        thread_ts=m.get("thread_ts"),
        parent_user_id=m.get("parent_user_id"),
        subtype=m.get("subtype"),
    )
    upsert(msg)
    for r in m.get("reactions", []):
        for uid in r.get("users", []):
            react = Reaction(
                message_ts=msg.ts,
                name=r.get("name"),
                count=r.get("count", 0),
                user_id=uid
            )
            upsert(react)

def fetch_thread_replies(client, channel_id, thread_ts):
    cursor = None
    while True:
        resp = safe_call(client.conversations_replies,
                         channel=channel_id,
                         ts=thread_ts,
                         cursor=cursor,
                         limit=200)
        for rm in resp["messages"]:
            if rm["ts"] == thread_ts:
                continue
            store_message(rm, channel_id)
        db.session.commit()
        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break

def fetch_messages_for_channel(client, channel_id, fetch_threads, oldest_ts, latest_ts, progress=None):
    cursor = None
    total = 0
    while True:
        resp = safe_call(client.conversations_history,
                         channel=channel_id,
                         cursor=cursor,
                         limit=200,
                         oldest=oldest_ts,
                         latest=latest_ts or None)
        msgs = resp["messages"]
        for m in msgs:
            store_message(m, channel_id)
            total += 1
        db.session.commit()
        if progress:
            progress["messages"][channel_id] = total

        if fetch_threads:
            for m in msgs:
                if m.get("reply_count", 0) > 0 and m.get("thread_ts"):
                    fetch_thread_replies(client, channel_id, m["thread_ts"])

        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break

def run_sync(selected_channel_ids, progress):
    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise RuntimeError("SLACK_TOKEN missing")
    fetch_threads = env_bool("FETCH_THREADS", True)
    oldest_ts = os.getenv("OLDEST_TS", "0").strip() or "0"
    latest_ts = os.getenv("LATEST_TS", "").strip()
    types = os.getenv("SLACK_TYPES", "public_channel,private_channel")

    client = WebClient(token=token)

    # Users
    progress["phase"] = "users"
    fetch_users(client, progress)

    # Channels (info / store)
    progress["phase"] = "channels"
    for cid in selected_channel_ids:
        info = safe_call(client.conversations_info, channel=cid)["channel"]
        store_channel(info)
    db.session.commit()

    # Messages
    progress["phase"] = "messages"
    progress["messages"] = {}
    for cid in selected_channel_ids:
        fetch_messages_for_channel(client, cid, fetch_threads, oldest_ts, latest_ts, progress)

    progress["phase"] = "done"
    db.session.commit()
