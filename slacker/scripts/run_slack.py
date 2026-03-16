#!/usr/bin/env python3
"""
Slack code-mode runner.

Accepts Python code via --code argument or stdin, executes it with
slack_sdk pre-imported and a configured Slack client available as `slack`.

Environment:
  SLACK_BOT_TOKEN - Slack Bot User OAuth Token.
  SLACK_USER_TOKEN - Slack User OAuth Token (for user-scope APIs).
  At least one must be set.
"""

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv


CACHE_FILE = Path(__file__).parent.parent / ".cache" / "lookups.json"


class LookupCache:
    """Simple JSON file cache for user/channel lookups."""

    def __init__(self, path: Path):
        self.path = path
        self._data = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                return {"users": {}, "channels": {}, "styles": {}}
        return {"users": {}, "channels": {}, "styles": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def get_user(self, key: str):
        """Get cached user by name, email, or ID."""
        return self._data["users"].get(key.lower())

    def set_user(self, key: str, value: dict):
        self._data["users"][key.lower()] = value
        self._save()

    def get_channel(self, key: str):
        """Get cached channel by name or ID."""
        return self._data["channels"].get(key.lower().lstrip("#"))

    def set_channel(self, key: str, value: dict):
        self._data["channels"][key.lower().lstrip("#")] = value
        self._save()

    def get_style(self, user_key: str):
        """Get cached conversation style for a user."""
        return self._data.setdefault("styles", {}).get(user_key.lower())

    def set_style(self, user_key: str, value: dict):
        self._data.setdefault("styles", {})[user_key.lower()] = value
        self._save()


class SlackerError(Exception):
    """Raised when a slacker helper fails."""
    pass


def build_helpers(client, user_client, cache):
    """Build helper functions exposed to user code."""

    def _resolve_users_bulk(user_ids):
        """Prefetch and cache multiple user IDs in one users_list call."""
        uncached = [uid for uid in set(user_ids) if not cache.get_user(uid)]
        if not uncached:
            return
        members = client.users_list(limit=500).get("members", [])
        for u in members:
            if u.get("deleted") or u.get("is_bot"):
                continue
            result = {"id": u["id"], "name": u["name"], "real_name": u.get("real_name", u["name"])}
            cache.set_user(u["id"], result)
            cache.set_user(u["name"].lower(), result)
            cache.set_user(u.get("real_name", "").lower(), result)

    def resolve_user(name_or_email: str) -> dict:
        """Resolve a user by name, email, or ID. Returns {id, name, real_name}.
        Results are cached."""
        cached = cache.get_user(name_or_email)
        if cached:
            return cached

        # If it looks like a user ID, fetch directly
        if name_or_email.startswith("U") and len(name_or_email) > 5:
            try:
                info = client.users_info(user=name_or_email)
                u = info["user"]
                result = {"id": u["id"], "name": u["name"], "real_name": u.get("real_name", u["name"])}
                cache.set_user(name_or_email, result)
                cache.set_user(u["name"].lower(), result)
                cache.set_user(u.get("real_name", "").lower(), result)
                return result
            except Exception:
                pass

        # If it looks like an email
        if "@" in name_or_email:
            try:
                info = client.users_lookupByEmail(email=name_or_email)
                u = info["user"]
                result = {"id": u["id"], "name": u["name"], "real_name": u.get("real_name", u["name"])}
                cache.set_user(name_or_email, result)
                cache.set_user(u["name"].lower(), result)
                cache.set_user(u.get("real_name", "").lower(), result)
                return result
            except Exception:
                pass

        # Search by name
        query = name_or_email.lower()
        users = client.users_list(limit=500)
        for u in users["members"]:
            if u.get("deleted") or u.get("is_bot"):
                continue
            real_name = u.get("real_name", "").lower()
            display_name = u.get("name", "").lower()
            if query in real_name or query in display_name:
                result = {"id": u["id"], "name": u["name"], "real_name": u.get("real_name", u["name"])}
                cache.set_user(query, result)
                cache.set_user(u["name"].lower(), result)
                cache.set_user(real_name, result)
                return result

        raise SlackerError(f"User '{name_or_email}' not found")

    def resolve_channel(name_or_id: str) -> dict:
        """Resolve a channel by name or ID. Returns {id, name}.
        Results are cached."""
        clean = name_or_id.lower().lstrip("#")
        cached = cache.get_channel(clean)
        if cached:
            return cached

        # If it looks like a channel ID
        if name_or_id.startswith("C") and len(name_or_id) > 5:
            try:
                info = client.conversations_info(channel=name_or_id)
                ch = info["channel"]
                result = {"id": ch["id"], "name": ch.get("name", ch["id"])}
                cache.set_channel(name_or_id, result)
                cache.set_channel(ch.get("name", ""), result)
                return result
            except Exception:
                pass

        # Search by name across all types
        for types in ["public_channel,private_channel", "im,mpim"]:
            cursor = None
            while True:
                kwargs = {"types": types, "limit": 200}
                if cursor:
                    kwargs["cursor"] = cursor
                convos = client.conversations_list(**kwargs)
                for ch in convos["channels"]:
                    ch_name = ch.get("name", "").lower()
                    if ch_name == clean or ch["id"].lower() == clean:
                        result = {"id": ch["id"], "name": ch.get("name", ch["id"])}
                        cache.set_channel(clean, result)
                        cache.set_channel(ch["id"].lower(), result)
                        return result
                cursor = convos.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        # Try DMs — resolve user name first then find DM
        user = resolve_user(name_or_id)
        if "id" in user and "error" not in user:
            try:
                dm = client.conversations_open(users=[user["id"]])
                result = {"id": dm["channel"]["id"], "name": f"DM with {user['real_name']}"}
                cache.set_channel(clean, result)
                return result
            except Exception:
                pass

        raise SlackerError(f"Channel '{name_or_id}' not found")

    def paginate(method, key, **kwargs):
        """Auto-paginate a Slack API method. Returns all items.

        Usage: all_messages = paginate(slack.conversations_history, "messages", channel="C01ABC", limit=200)
        """
        all_items = []
        cursor = None
        while True:
            if cursor:
                kwargs["cursor"] = cursor
            response = method(**kwargs)
            all_items.extend(response.get(key, []))
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return all_items

    _my_id_cache = {}

    def my_id():
        """Get the authenticated user's ID. Cached."""
        if "id" not in _my_id_cache:
            resp = client.auth_test()
            _my_id_cache["id"] = resp["user_id"]
            _my_id_cache["user"] = resp["user"]
            _my_id_cache["team"] = resp["team"]
        return _my_id_cache["id"]

    def send(channel_or_name, text, **kwargs):
        """Resolve channel by name/ID and send a message. Returns ts."""
        ch = resolve_channel(channel_or_name)
        result = client.chat_postMessage(channel=ch["id"], text=text, **kwargs)
        return result["ts"]

    def reply(channel_or_name, thread_ts, text, **kwargs):
        """Reply to a thread. Resolves channel by name/ID. Returns ts."""
        ch = resolve_channel(channel_or_name)
        result = client.chat_postMessage(channel=ch["id"], text=text, thread_ts=thread_ts, **kwargs)
        return result["ts"]

    def _resolve_msg_names(messages):
        """Bulk-resolve user names for a list of messages."""
        user_ids = [m.get("user", "") for m in messages if m.get("user")]
        _resolve_users_bulk(user_ids)
        result = []
        for msg in messages:
            uid = msg.get("user", "?")
            cached = cache.get_user(uid)
            name = cached["real_name"] if cached else uid
            result.append({"name": name, "text": msg.get("text", "")[:500], "ts": msg["ts"]})
        return result

    def read_conversation(channel_or_name, limit=15):
        """Read recent messages from a channel/DM with user names resolved.
        Returns list of {name, text, ts} dicts, oldest first."""
        ch = resolve_channel(channel_or_name)
        history = client.conversations_history(channel=ch["id"], limit=limit)
        msgs = _resolve_msg_names(history["messages"])
        msgs.reverse()
        return msgs

    def read_thread(channel_or_name, thread_ts, limit=50):
        """Read thread replies with user names resolved.
        Returns list of {name, text, ts} dicts, oldest first."""
        ch = resolve_channel(channel_or_name)
        resp = client.conversations_replies(channel=ch["id"], ts=thread_ts, limit=limit)
        return _resolve_msg_names(resp.get("messages", []))

    def get_unreads():
        """Get all channels/DMs with unread messages.
        Returns list of {name, id, unreads} dicts sorted by unread count desc."""
        convos = client.conversations_list(
            types="public_channel,private_channel,im,mpim", limit=200
        )
        unreads = []
        for ch in convos["channels"]:
            n = ch.get("unread_count_display", 0)
            if ch.get("is_member") and n > 0:
                unreads.append({"name": ch.get("name", ch["id"]), "id": ch["id"], "unreads": n})
        unreads.sort(key=lambda x: x["unreads"], reverse=True)
        return unreads

    def my_activity(since_hours=24):
        """Get all messages directed at the authenticated user in the last N hours.
        Checks DMs, group DMs, and @mentions. Returns list of {name, text, ts, channel} dicts sorted chronologically."""
        import time
        uid = my_id()
        oldest = str(time.time() - since_hours * 3600)

        activity = []

        # DMs and group DMs
        convos = client.conversations_list(types="im,mpim", limit=200)
        for ch in convos["channels"]:
            if not ch.get("is_member"):
                continue
            try:
                history = client.conversations_history(channel=ch["id"], oldest=oldest, limit=30)
            except Exception:
                continue
            for msg in history.get("messages", []):
                if msg.get("user") == uid:
                    continue
                msg_uid = msg.get("user", "?")
                cached = cache.get_user(msg_uid)
                if not cached:
                    try:
                        cached = resolve_user(msg_uid)
                    except SlackerError:
                        cached = {"real_name": msg_uid}
                activity.append({
                    "name": cached.get("real_name", msg_uid),
                    "text": msg.get("text", "")[:300],
                    "ts": msg["ts"],
                    "channel": ch.get("name", ch["id"]),
                })

        # @mentions in channels (requires user token)
        if user_client:
            try:
                results = user_client.search_messages(query=f"<@{uid}>", count=50)
                for m in results.get("messages", {}).get("matches", []):
                    if float(m.get("ts", 0)) < float(oldest):
                        continue
                    activity.append({
                        "name": m.get("username", "?"),
                        "text": m.get("text", "")[:300],
                        "ts": m["ts"],
                        "channel": m.get("channel", {}).get("name", "?"),
                    })
            except Exception:
                pass

        # Deduplicate by ts and sort chronologically
        seen = set()
        unique = []
        for item in activity:
            if item["ts"] not in seen:
                seen.add(item["ts"])
                unique.append(item)
        unique.sort(key=lambda x: float(x["ts"]))
        return unique

    return {
        "resolve_user": resolve_user,
        "resolve_channel": resolve_channel,
        "paginate": paginate,
        "my_id": my_id,
        "send": send,
        "reply": reply,
        "read_conversation": read_conversation,
        "read_thread": read_thread,
        "get_unreads": get_unreads,
        "my_activity": my_activity,
    }


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="Execute Python code with Slack SDK")
    parser.add_argument("--code", type=str, help="Python code to execute")
    parser.add_argument("--workspace", type=str, help="Workspace profile name (for multi-workspace)", default=None)
    args = parser.parse_args()

    code = args.code if args.code else sys.stdin.read()
    if not code.strip():
        print(json.dumps({"error": "No code provided"}))
        sys.exit(1)

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    user_token = os.environ.get("SLACK_USER_TOKEN")

    if not bot_token and not user_token:
        print(json.dumps({"error": "SLACK_BOT_TOKEN or SLACK_USER_TOKEN must be set"}))
        sys.exit(1)

    # Build execution namespace with pre-configured clients
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    primary_client = WebClient(token=bot_token) if bot_token else WebClient(token=user_token)
    user_client = WebClient(token=user_token) if user_token else None

    cache = LookupCache(CACHE_FILE)
    helpers = build_helpers(primary_client, user_client, cache)

    namespace = {
        "__builtins__": __builtins__,
        "json": json,
        "os": os,
        "slack": primary_client,
        "slack_user": user_client,
        "WebClient": WebClient,
        "SlackApiError": SlackApiError,
        "SlackerError": SlackerError,
        "cache": cache,
        **helpers,
    }

    try:
        # Wrap code in a function to capture return value
        wrapped = "def __run__():\n"
        for line in code.split("\n"):
            wrapped += f"    {line}\n"
        wrapped += "\n__result__ = __run__()"

        exec(wrapped, namespace)
        result = namespace.get("__result__")

        if result is not None:
            if isinstance(result, str):
                print(result)
            else:
                print(json.dumps(result, indent=2, default=str))
    except SlackerError as e:
        print(json.dumps({"error": "SlackerError", "message": str(e)}))
        sys.exit(1)
    except SlackApiError as e:
        print(json.dumps({
            "error": "Slack API Error",
            "message": str(e.response["error"]),
            "status": e.response.status_code,
        }))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({
            "error": type(e).__name__,
            "message": str(e),
            "traceback": traceback.format_exc(),
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
# test
