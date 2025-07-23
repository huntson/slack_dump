import os
import logging
from datetime import datetime, timezone
from tenacity import retry, wait_random_exponential, stop_after_attempt

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from .db import make_engine, make_session_factory, Base
from .models import Channel, User, Message, Reaction

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("slackdump")

# ------------- Slack helpers -------------
def env_bool(name, default=False):
    return str(os.getenv(name, str(default))).lower() in ("1", "true", "yes", "y")

@retry(wait=wait_random_exponential(multiplier=1, max=60), stop=stop_after_attempt(5))
def safe_call(func, **kwargs):
    return func(**kwargs)

def upsert(session, obj):
    try:
        session.merge(obj)
    except IntegrityError:
        session.rollback()
        session.merge(obj)

def fetch_users(client, session):
    log.info("Fetching users...")
    cursor = None
    while True:
        resp = safe_call(client.users_list, cursor=cursor, limit=200)
        for u in resp["members"]:
            user = User(
                id=u.get("id"),
                name=u.get("name"),
                real_name=u.get("real_name"),
                tz=u.get("tz"),
            )
            upsert(session, user)
        session.commit()
        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break
    log.info("Users done.")

def get_channel_map(client):
    mapping = {}  # name->id & id->name
    cursor = None
    while True:
        resp = safe_call(client.conversations_list, cursor=cursor, limit=200, types="public_channel,private_channel")
        for c in resp["channels"]:
            mapping[c["name"]] = c["id"]
            mapping[c["id"]] = c["name"]
        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break
    return mapping

def store_channel(session, slack_chan):
    ch = Channel(
        id=slack_chan["id"],
        name=slack_chan.get("name"),
        is_private=slack_chan.get("is_private", False),
        created=datetime.fromtimestamp(slack_chan.get("created", 0), tz=timezone.utc) if slack_chan.get("created") else None,
    )
    upsert(session, ch)

def fetch_channel_info(client, channel_id):
    resp = safe_call(client.conversations_info, channel=channel_id)
    return resp["channel"]

def fetch_messages_for_channel(client, session, channel_id, fetch_threads, oldest_ts, latest_ts):
    log.info(f"Fetching messages for channel {channel_id} ...")
    cursor = None
    while True:
        resp = safe_call(client.conversations_history,
                         channel=channel_id,
                         cursor=cursor,
                         limit=200,
                         oldest=oldest_ts,
                         latest=latest_ts or None)
        msgs = resp["messages"]
        for m in msgs:
            store_message(session, m, channel_id)
        session.commit()

        if fetch_threads:
            for m in msgs:
                if m.get("reply_count", 0) > 0 and m.get("thread_ts"):
                    fetch_thread_replies(client, session, channel_id, m["thread_ts"])

        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break

def store_message(session, m, channel_id):
    msg = Message(
        ts=m["ts"],
        channel_id=channel_id,
        user_id=m.get("user"),
        text=m.get("text"),
        thread_ts=m.get("thread_ts"),
        parent_user_id=m.get("parent_user_id"),
        subtype=m.get("subtype"),
    )
    upsert(session, msg)

    # reactions
    for r in m.get("reactions", []):
        # Slack reaction has 'name', 'count', 'users' list
        for uid in r.get("users", []):
            react = Reaction(
                message_ts=msg.ts,
                name=r.get("name"),
                count=r.get("count", 0),
                user_id=uid
            )
            upsert(session, react)

def fetch_thread_replies(client, session, channel_id, thread_ts):
    cursor = None
    while True:
        resp = safe_call(client.conversations_replies,
                         channel=channel_id,
                         ts=thread_ts,
                         cursor=cursor,
                         limit=200)
        for rm in resp["messages"]:
            if rm["ts"] == thread_ts:
                # parent already stored by history call
                continue
            store_message(session, rm, channel_id)
        session.commit()

        cursor = resp["response_metadata"].get("next_cursor")
        if not cursor:
            break

def main():
    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise SystemExit("SLACK_TOKEN env var missing")

    channels_env = os.getenv("SLACK_CHANNELS", "*").strip()
    fetch_threads = env_bool("FETCH_THREADS", True)

    oldest_ts = os.getenv("OLDEST_TS", "0").strip() or "0"
    latest_ts = os.getenv("LATEST_TS", "").strip()

    # DB
    engine = make_engine(
        os.getenv("DB_USER", "slack"),
        os.getenv("DB_PASSWORD", "slack"),
        os.getenv("DB_HOST", "db"),
        os.getenv("DB_PORT", "5432"),
        os.getenv("DB_NAME", "slackdump"),
    )
    Base.metadata.create_all(engine)
    Session = make_session_factory(engine)

    client = WebClient(token=token)

    with Session() as session:
        # users first (reactions reference them)
        fetch_users(client, session)

        # channels
        chan_map = get_channel_map(client)

        # Determine target channels
        if channels_env == "*":
            target_ids = [cid for cid, name in chan_map.items() if cid.startswith("C") or cid.startswith("G")]
        else:
            requested = [c.strip() for c in channels_env.split(",") if c.strip()]
            target_ids = []
            for name_or_id in requested:
                target_ids.append(chan_map.get(name_or_id, name_or_id))  # fallback if raw id

        # Store channel info
        for cid in target_ids:
            info = fetch_channel_info(client, cid)
            store_channel(session, info)
        session.commit()

        # messages
        for cid in target_ids:
            fetch_messages_for_channel(client, session, cid, fetch_threads, oldest_ts, latest_ts)

    log.info("Done.")

if __name__ == "__main__":
    main()
