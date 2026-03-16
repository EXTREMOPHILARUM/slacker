---
name: slack
description: "Slack integration — send messages, read channels/DMs, search, check unreads, post Block Kit messages, manage users/reactions/threads, and any Slack operation via code-mode.
TRIGGER when: user mentions Slack, messages, DMs, channels, unreads, sending messages, checking messages, posting to Slack, Slack notifications, Block Kit, thread replies, reactions, or any Slack workspace interaction.
DO NOT TRIGGER when: user is discussing messaging in general code (e.g. message queues, pub/sub), or Slack is mentioned only in documentation/comments being edited."
trigger-keywords: ["slack", "dm", "direct message", "channel", "unreads", "send message", "check messages", "block kit", "thread", "reaction", "slack message", "post to slack", "slack notification"]
user-invocable: true
---

# Slack Code-Mode

Write and execute Python code using the `slack_sdk` library to interact with Slack.

## How to use

Run the code using:
```bash
cd ~/.claude/plugins/marketplaces/slacker/slacker && uv run python scripts/run_slack.py --code '<python_code>'
```

For multi-line code, use a heredoc:
```bash
cd ~/.claude/plugins/marketplaces/slacker/slacker && uv run python scripts/run_slack.py --code "$(cat <<'PYEOF'
# your python code here
PYEOF
)"
```

## Pre-configured globals

The runner provides these pre-configured objects:

- `slack` — `slack_sdk.WebClient` authenticated with `SLACK_BOT_TOKEN` (falls back to user token)
- `slack_user` — `slack_sdk.WebClient` authenticated with `SLACK_USER_TOKEN` (if set)
- `SlackApiError` — Exception class for Slack API errors
- `SlackerError` — Exception class raised by helpers when resolution fails (e.g. user/channel not found)
- `json` — Python json module
- `os` — Python os module
- `resolve_user(name_or_email)` — Resolve a user by name, email, or ID. Returns `{"id", "name", "real_name"}`. Cached.
- `resolve_channel(name_or_id)` — Resolve a channel by name (with or without #), ID, or even a person's name (finds their DM). Returns `{"id", "name"}`. Cached.
- `paginate(method, key, **kwargs)` — Auto-paginate any Slack API method. Returns all items across all pages.
- `my_id()` — Get the authenticated user's ID. Cached after first call.
- `send(channel_or_name, text, **kwargs)` — Resolve channel + send message in one call. Returns `ts`. Accepts any `chat_postMessage` kwargs (blocks, etc).
- `reply(channel_or_name, thread_ts, text, **kwargs)` — Reply to a thread. Resolves channel, posts with `thread_ts`. Returns `ts`.
- `read_conversation(channel_or_name, limit=15)` — Read recent messages with user names resolved. Returns `[{name, text, ts}]` oldest-first, text capped at 500 chars.
- `read_thread(channel_or_name, thread_ts, limit=50)` — Read thread replies with user names resolved. Returns `[{name, text, ts}]` oldest-first.
- `get_unreads()` — Get all channels/DMs with unread messages. Returns `[{name, id, unreads}]` sorted by unread count desc.
- `my_activity(since_hours=24)` — Get all messages directed at you (DMs, group DMs, @mentions) in the last N hours. Returns `[{name, text, ts, channel}]` sorted chronologically. Deduped.
- `cache` — Direct access to the lookup cache if needed
  - `cache.get_style(user_key)` — Get cached conversation style profile for a user (by name, ID, or email). Returns a dict or `None`.
  - `cache.set_style(user_key, profile_dict)` — Save a conversation style profile for a user. Persists across runs.

### Helper examples

**resolve_user** — no more manual user list scanning:
```python
jane = resolve_user("jane")
return f"{jane['real_name']} = {jane['id']}"
# Cached — instant on second call
```

**resolve_channel** — works with names, IDs, or DM targets:
```python
ch = resolve_channel("#engineering")       # by name
ch = resolve_channel("C04PMH8RSSV")    # by ID
ch = resolve_channel("jane")          # finds DM with jane
return ch
```

**paginate** — no more cursor boilerplate:
```python
# Get ALL members of a channel (even if 500+)
all_members = paginate(slack.conversations_members, "members", channel="C04PMH8RSSV", limit=200)
return f"{len(all_members)} members"

# Get ALL messages (careful — can be large)
all_msgs = paginate(slack.conversations_history, "messages", channel="C04PMH8RSSV", limit=200)
return f"{len(all_msgs)} messages"
```

**my_id** — get authenticated user without boilerplate:
```python
me = my_id()
return f"I am {me}"
```

**send** — resolve + post in one call:
```python
ts = send("#team-updates", "Deploy v2.3.1 complete")
return f"Sent (ts: {ts})"

# Send to a person's DM
ts = send("jane", "hey, quick question")
```

**reply** — respond in a thread:
```python
ts = reply("#team-updates", "1234567890.123456", "Done, deployed to staging")
return f"Replied (ts: {ts})"
```

**read_conversation** — fetch messages with names resolved:
```python
msgs = read_conversation("jane", limit=20)
lines = [f"[{m['name']}] {m['text']}" for m in msgs]
return "\n".join(lines)
```

**read_thread** — fetch thread replies:
```python
msgs = read_thread("#engineering", "1234567890.123456")
lines = [f"[{m['name']}] {m['text']}" for m in msgs]
return "\n".join(lines)
```

**get_unreads** — check all unread channels at once:
```python
unreads = get_unreads()
if not unreads:
    return "No unreads"
lines = ["channel\tunread"]
for u in unreads:
    lines.append(f"{u['name']}\t{u['unreads']}")
return "\n".join(lines)
```

**my_activity** — everything directed at you:
```python
# Last 8 hours of DMs + @mentions
items = my_activity(since_hours=8)
if not items:
    return "Nothing new"
lines = [f"[{a['name']}] #{a['channel']}: {a['text']}" for a in items]
return "\n".join(lines)
```

**IMPORTANT: Always prefer helpers over raw API calls:**
- Use `resolve_user("jane")` instead of scanning `users_list` manually
- Use `resolve_channel("#engineering")` instead of scanning `conversations_list`
- Use `paginate()` instead of writing cursor loops
- Use `send()` instead of `resolve_channel` + `chat_postMessage`
- Use `reply()` instead of `send()` with `thread_ts` for thread replies
- Use `read_conversation()` instead of `conversations_history` + user resolution loops
- Use `my_id()` instead of `auth_test()['user_id']`
- Use `read_thread()` instead of `conversations_replies` + user resolution loops
- Use `get_unreads()` instead of manually scanning `conversations_list` for unread counts
- Use `my_activity()` instead of manually combining DMs + search for @mentions
- Helpers raise `SlackerError` on failure — no need to check for error dicts
- Helpers are cached — repeated calls are instant

## Code pattern

Write code as a function body. Use `return` to send results back. If you return a string it prints raw, otherwise it prints as JSON.

## Output formatting — minimize tokens

ALWAYS format return values for minimal token usage. Choose the leanest format for the data:

**Chat/messages** — return a plain string with one line per message:
```python
lines = []
for msg in messages:
    lines.append(f"[{name}] {msg['text']}")
return "\n".join(lines)
```

**Tabular data** (channels, users, lists) — return a plain TSV string:
```python
rows = ["id\tname"]
for ch in channels:
    rows.append(f"{ch['id']}\t{ch['name']}")
return "\n".join(rows)
```

**Single values** — return a plain string:
```python
return f"Message sent to {channel} (ts: {result['ts']})"
```

**Complex nested data** — only use dicts/lists when structure genuinely matters. Even then, trim to only the fields needed.

**Rules:**
- Never return raw API responses — they contain dozens of unused fields
- Pick only the fields the user needs
- Prefer `return "string"` over `return {"key": "value"}` when possible
- Cap text fields (e.g. `msg['text'][:300]`) to avoid dumping huge messages
- Use `limit` params aggressively to reduce API payloads
- **Never add branding, attribution, or "sent via" footers** to messages. No "Posted via slacker", no robot emoji signatures. Messages should look like the user wrote them.

## Available Slack SDK methods

### Messaging
- `slack.chat_postMessage(channel, text, blocks=None, thread_ts=None, unfurl_links=False)` — Send a message
- `slack.chat_update(channel, ts, text=None, blocks=None)` — Update a message
- `slack.chat_delete(channel, ts)` — Delete a message
- `slack.chat_postEphemeral(channel, user, text)` — Send ephemeral message

### Channels & Conversations
- `slack.conversations_list(types="public_channel,private_channel", limit=200)` — List channels
- `slack.conversations_info(channel=channel_id)` — Get channel info
- `slack.conversations_history(channel=channel_id, limit=20)` — Get channel messages
- `slack.conversations_replies(channel=channel_id, ts=thread_ts)` — Get thread replies
- `slack.conversations_join(channel=channel_id)` — Join a channel
- `slack.conversations_create(name="channel-name", is_private=False)` — Create channel
- `slack.conversations_archive(channel=channel_id)` — Archive channel
- `slack.conversations_mark(channel=channel_id, ts=timestamp)` — Mark as read

### Search (requires user token)
- `slack_user.search_messages(query="search terms", count=20)` — Search messages
- `slack_user.search_files(query="search terms")` — Search files

### Users
- `slack.users_list(limit=200)` — List workspace users
- `slack.users_info(user=user_id)` — Get user info
- `slack.users_lookupByEmail(email="user@example.com")` — Find user by email
- `slack.users_profile_get(user=user_id)` — Get user profile

### Reactions
- `slack.reactions_add(channel=channel_id, timestamp=msg_ts, name="thumbsup")` — Add reaction
- `slack.reactions_remove(channel=channel_id, timestamp=msg_ts, name="thumbsup")` — Remove reaction
- `slack.reactions_get(channel=channel_id, timestamp=msg_ts)` — Get reactions on a message

### Files
- `slack.files_upload_v2(channel=channel_id, file=path, title="File")` — Upload file
- `slack.files_list(channel=channel_id)` — List files
- `slack.files_info(file=file_id)` — Get file info

### User Groups
- `slack.usergroups_list(include_users=True)` — List user groups
- `slack.usergroups_create(name="Group", handle="group-handle")` — Create group
- `slack.usergroups_update(usergroup=group_id, name="New Name")` — Update group
- `slack.usergroups_users_list(usergroup=group_id)` — List group members
- `slack.usergroups_users_update(usergroup=group_id, users=["U1","U2"])` — Set group members

### Bookmarks
- `slack.bookmarks_list(channel_id=channel_id)` — List channel bookmarks
- `slack.bookmarks_add(channel_id=channel_id, title="Title", type="link", link="https://...")` — Add bookmark

### Pins
- `slack.pins_add(channel=channel_id, timestamp=msg_ts)` — Pin a message
- `slack.pins_remove(channel=channel_id, timestamp=msg_ts)` — Unpin a message
- `slack.pins_list(channel=channel_id)` — List pinned items

### Reminders
- `slack.reminders_add(text="Do thing", time="in 10 minutes")` — Create reminder
- `slack.reminders_list()` — List reminders

## Examples

### Check my activity / what I received
```python
items = my_activity(since_hours=8)
if not items:
    return "Nothing new"
lines = [f"[{a['name']}] #{a['channel']}: {a['text']}" for a in items]
return "\n".join(lines)
```

### Check unreads
```python
unreads = get_unreads()
if not unreads:
    return "No unreads"
lines = ["channel\tunread"]
for u in unreads:
    lines.append(f"{u['name']}\t{u['unreads']}")
return "\n".join(lines)
```

### Send a message
```python
ts = send("#team-updates", "Deploy v2.3.1 complete")
return f"Sent to #team-updates (ts: {ts})"
```

### Read a DM or channel
```python
msgs = read_conversation("jane", limit=15)
return "\n".join(f"[{m['name']}] {m['text']}" for m in msgs)
```

### Search messages
```python
results = slack_user.search_messages(query="bug report from:alex", count=5)
matches = results["messages"]["matches"]
if not matches:
    return "No messages found"
lines = []
for m in matches:
    lines.append(f"[{m['username']}] #{m['channel']['name']}: {m['text'][:200]}")
return "\n".join(lines)
```

### List channel members
```python
members = slack.conversations_members(channel="C01ABCDEF", limit=200)
rows = ["id\tname\thandle"]
for uid in members["members"]:
    u = slack.users_info(user=uid)["user"]
    rows.append(f"{uid}\t{u['real_name']}\t{u['name']}")
return "\n".join(rows)
```

### Replying on behalf of the user

When the user asks you to reply, respond, or auto-reply to someone on Slack — whether one-off or via a cron loop — you MUST match the user's natural conversation style with that specific person. Never use generic or formal language.

**Before sending any reply, check the style cache first:**

1. **Check cache** — call `cache.get_style(person_name)`. If a cached style profile exists, use it directly (skip to step 4).
2. **Fetch conversation history** (cache miss only) — read 30-50 recent messages from the conversation to understand how the user talks to this person
3. **Analyze and cache the style** — identify the following, then save with `cache.set_style(person_name, profile)`:
   - `language`: primary language(s) and code-switching patterns
   - `tone`: teasing, formal, casual, supportive, etc.
   - `message_length`: short/medium/long typical message length
   - `emoji_style`: which emojis used and how frequently
   - `slang`: common abbreviations, slang, filler words
   - `nicknames`: pet names or terms of address for this person
   - `example_phrases`: 3-5 representative snippets from the user's actual messages
   - `cultural_context`: mixed languages, inside jokes, references
4. **Match the style exactly** — your reply should be indistinguishable from the user's own messages in that conversation
5. **Never sound like an AI** — no corporate phrasing, no bullet points, no "I hope this helps", no over-politeness that doesn't match the conversation tone

**Style cache example:**
```python
# Check for cached style
style = cache.get_style("jane")
if not style:
    # Analyze conversation and build profile
    style = {
        "language": "English with Hindi words mixed in",
        "tone": "casual, teasing",
        "message_length": "short, 1-2 sentences",
        "emoji_style": "rare, mostly 😂 and 👍",
        "slang": "gonna, nah, lol, btw",
        "nicknames": "bro, dude",
        "example_phrases": ["lol nah that's broken", "dude just ship it", "acha theek hai"],
        "cultural_context": "Hinglish code-switching common"
    }
    cache.set_style("jane", style)
# Now use `style` to craft the reply
```

**For cron-based auto-replies:**
- First run loads from cache or analyzes + caches
- All subsequent runs reuse the cached style — no repeated API calls
- If the user says the style is off, delete with `cache.set_style(person, None)` to force re-analysis

**What NOT to do:**
- Don't use formal English if the user chats casually
- Don't add emojis the user never uses
- Don't write long messages if the user sends short ones
- Don't hardcode style rules — always derive from actual conversation history
- Don't re-analyze style every time — use the cache

## Block Kit — rich message layouts

Use `blocks` param on `chat_postMessage`/`chat_update` for rich messages. `text` is the notification fallback. Max 50 blocks per message, 100 in modals/Home tabs.

### Layout blocks (16 types)

#### Header
Large bold text. Max 150 chars. Plain text only.
```python
{"type": "header", "text": {"type": "plain_text", "text": ":rocket: Deploy Complete"}}
```

#### Section
Most versatile block. Supports text, fields (2-col grid), and an accessory element.
- `text`: mrkdwn or plain_text, max 3000 chars
- `fields`: array of text objects, max 10 items, 2000 chars each (renders as 2-column grid)
- `accessory`: any interactive element (button, overflow, datepicker, image, select, checkbox, radio, timepicker)
- `expand`: boolean — force full text display without "see more" truncation
```python
# Text + fields + accessory combo
{"type": "section",
 "text": {"type": "mrkdwn", "text": "*Task Dashboard*"},
 "fields": [
     {"type": "mrkdwn", "text": "*Status:*\n:large_green_circle: Active"},
     {"type": "mrkdwn", "text": "*Priority:*\n:red_circle: Urgent"},
     {"type": "mrkdwn", "text": "*Assignee:*\n<@U01EXAMPLE>"},
     {"type": "mrkdwn", "text": "*Due:*\n2026-03-17"}
 ],
 "accessory": {"type": "overflow", "action_id": "overflow_1", "options": [
     {"text": {"type": "plain_text", "text": ":pencil: Edit"}, "value": "edit"},
     {"text": {"type": "plain_text", "text": ":wastebasket: Archive"}, "value": "archive"}
 ]}}
```

#### Divider
Horizontal rule. No properties.
```python
{"type": "divider"}
```

#### Context
Small grey metadata line. Max 10 elements. Supports images and text objects.
```python
{"type": "context", "elements": [
    {"type": "image", "image_url": "https://avatars.slack-edge.com/user.png", "alt_text": "avatar"},
    {"type": "mrkdwn", "text": "<@U01EXAMPLE> | March 16, 2026 | :white_check_mark: Verified"}
]}
```

#### Image
Standalone image. Supports `image_url` (public URL) or `slack_file` (Slack-hosted). PNG/JPG/GIF.
```python
{"type": "image", "image_url": "https://charts.example.com/weekly.png",
 "alt_text": "Weekly metrics chart", "title": {"type": "plain_text", "text": "Metrics — Week 11"}}
```

#### Actions
Row of interactive elements. Max 25 elements. Supports: buttons, selects, multi-selects, overflow, datepicker, datetimepicker, timepicker, checkboxes, radio buttons.
```python
{"type": "actions", "elements": [
    {"type": "button", "text": {"type": "plain_text", "text": ":white_check_mark: Approve"}, "style": "primary", "action_id": "approve", "value": "task_123"},
    {"type": "button", "text": {"type": "plain_text", "text": ":x: Reject"}, "style": "danger", "action_id": "reject", "confirm": {
        "title": {"type": "plain_text", "text": "Are you sure?"},
        "text": {"type": "mrkdwn", "text": "This will reject the task permanently."},
        "confirm": {"type": "plain_text", "text": "Yes, reject"},
        "deny": {"type": "plain_text", "text": "Cancel"},
        "style": "danger"
    }},
    {"type": "static_select", "placeholder": {"type": "plain_text", "text": "Reassign..."}, "action_id": "assign",
     "option_groups": [
         {"label": {"type": "plain_text", "text": "Engineering"}, "options": [
             {"text": {"type": "plain_text", "text": "Member A"}, "value": "U01"},
             {"text": {"type": "plain_text", "text": "Member B"}, "value": "U02"}
         ]},
         {"label": {"type": "plain_text", "text": "Design"}, "options": [
             {"text": {"type": "plain_text", "text": "Member C"}, "value": "U03"}
         ]}
     ]}
]}
```

#### Rich Text
Structured formatted text with deep nesting. The most powerful text block — supports styled text, lists, code blocks, quotes, mentions, links, emoji, colors, dates, and usergroups.

**Container types:**
- `rich_text_section` — inline content with mixed styles
- `rich_text_list` — bullet or ordered lists (props: `style`="bullet"|"ordered", `indent`, `offset`, `border`)
- `rich_text_preformatted` — code blocks (props: `border`, `language` for syntax highlighting e.g. "python", "javascript", "sql")
- `rich_text_quote` — block quotes (props: `border`)

**Element types within containers:**
- `text` — `{"type":"text", "text":"...", "style":{"bold":true, "italic":true, "strike":true, "code":true, "underline":true}}`
- `user` — `{"type":"user", "user_id":"U01ABC"}`
- `channel` — `{"type":"channel", "channel_id":"C01ABC"}`
- `emoji` — `{"type":"emoji", "name":"fire"}`
- `link` — `{"type":"link", "url":"https://...", "text":"display text", "style":{"bold":true}}`
- `broadcast` — `{"type":"broadcast", "range":"here"|"channel"|"everyone"}`
- `color` — `{"type":"color", "value":"#FF5733"}`
- `date` — `{"type":"date", "timestamp":1710590400, "format":"{date_long} at {time}", "fallback":"March 16"}`
- `usergroup` — `{"type":"usergroup", "usergroup_id":"G01ABC"}`

```python
{"type": "rich_text", "elements": [
    {"type": "rich_text_section", "elements": [
        {"type": "text", "text": "Sprint Review ", "style": {"bold": True}},
        {"type": "emoji", "name": "memo"},
        {"type": "text", "text": " — "},
        {"type": "date", "timestamp": 1710590400, "format": "{date_long}", "fallback": "March 16, 2026"}
    ]},
    {"type": "rich_text_list", "style": "bullet", "elements": [
        {"type": "rich_text_section", "elements": [
            {"type": "text", "text": "Shipped ", "style": {"bold": True}},
            {"type": "text", "text": "Heimdall PII proxy to production"}
        ]},
        {"type": "rich_text_section", "elements": [
            {"type": "text", "text": "Resolved "},
            {"type": "link", "url": "https://app.clickup.com/t/86d29ndmd", "text": "PIP install bug"}
        ]}
    ]},
    {"type": "rich_text_preformatted", "language": "python", "elements": [
        {"type": "text", "text": "slack.chat_postMessage(channel='#engineering', text='hello')"}
    ]},
    {"type": "rich_text_quote", "elements": [
        {"type": "text", "text": "Two more AE groups are asking for the same presentation", "style": {"italic": True}},
        {"type": "text", "text": " — "},
        {"type": "user", "user_id": "U02EXAMPLE"}
    ]}
]}
```

#### Table
Tabular data with up to 100 rows × 20 columns. One table per message. Cells support rich text formatting (bold, emoji, mentions, links).

- `rows`: array of row arrays. Each cell is `{"type":"rich_text", "elements":[...]}` or `{"type":"raw_text", "text":"..."}`
- `column_settings`: array of `{"align":"left"|"center"|"right", "is_wrapped":true|false}`
```python
{"type": "table",
 "column_settings": [
     {"align": "left"},
     {"align": "left"},
     {"align": "center"},
     {"align": "right"}
 ],
 "rows": [
     [{"type":"raw_text","text":"Task"}, {"type":"raw_text","text":"Status"}, {"type":"raw_text","text":"Priority"}, {"type":"raw_text","text":"Due"}],
     [{"type":"rich_text","elements":[{"type":"rich_text_section","elements":[
         {"type":"link","url":"https://app.clickup.com/t/123","text":"PIP install fix"}
     ]}]},
      {"type":"raw_text","text":":hammer_and_wrench: In Progress"},
      {"type":"raw_text","text":":red_circle: Urgent"},
      {"type":"raw_text","text":"Mar 12"}],
     [{"type":"rich_text","elements":[{"type":"rich_text_section","elements":[
         {"type":"link","url":"https://app.clickup.com/t/456","text":"SF CLI Audit"}
     ]}]},
      {"type":"raw_text","text":":hammer_and_wrench: In Progress"},
      {"type":"raw_text","text":":large_orange_circle: High"},
      {"type":"raw_text","text":"Mar 12"}]
 ]}
```

#### Markdown
Standard markdown block. Useful for LLM-generated content. Supports: bold, italic, headers, links, ordered/unordered lists, strikethrough, inline code, code blocks with syntax highlighting, blockquotes, horizontal dividers, tables, task lists. Max 12,000 chars cumulative across all markdown blocks.
```python
{"type": "markdown", "text": "**Sprint Summary**\n\n| Task | Status |\n|------|--------|\n| Heimdall | :white_check_mark: Done |\n| VPN Migration | :hourglass: In Progress |\n\n---\n\n- [x] Deploy complete\n- [ ] Tests pending"}
```

#### Video
Embeds video with thumbnail. Requires `links.embed:write` scope. HTTPS only.
```python
{"type": "video", "title": {"type": "plain_text", "text": "Demo Recording"},
 "video_url": "https://www.youtube.com/embed/ABC123?autoplay=1",
 "thumbnail_url": "https://i.ytimg.com/vi/ABC123/hqdefault.jpg",
 "alt_text": "Product demo", "title_url": "https://youtube.com/watch?v=ABC123",
 "description": {"type": "plain_text", "text": "Q1 product demo walkthrough"},
 "author_name": "Team", "provider_name": "YouTube"}
```

#### Input (modals/Home tabs only)
Collects user input. Supports: plain_text_input, email_input, url_input, number_input, datepicker, datetimepicker, timepicker, static_select, multi_select, checkboxes, radio_buttons, rich_text_input, file_input.
```python
{"type": "input", "label": {"type": "plain_text", "text": "Description"},
 "element": {"type": "rich_text_input", "action_id": "desc"},
 "hint": {"type": "plain_text", "text": "Provide details about the issue"},
 "optional": False, "dispatch_action": True}
```

#### File
Displays a remote file. Requires `remote_files:share` scope.
```python
{"type": "file", "external_id": "ABCDE12345", "source": "remote"}
```

### Interactive elements reference

**Button** — `"style"`: none (grey), `"primary"` (green), `"danger"` (red). Add `"url"` for link buttons. Add `"confirm"` for confirmation dialog.
```python
{"type": "button", "text": {"type": "plain_text", "text": ":rocket: Deploy"},
 "style": "primary", "action_id": "deploy", "value": "v2.3.1",
 "url": "https://deploy.example.com/v2.3.1"}
```

**Overflow menu** — compact "..." menu for secondary actions:
```python
{"type": "overflow", "action_id": "more", "options": [
    {"text": {"type": "plain_text", "text": ":pencil: Edit"}, "value": "edit"},
    {"text": {"type": "plain_text", "text": ":wastebasket: Delete"}, "value": "delete"}
]}
```

**Static select** — dropdown. Supports `options` or `option_groups`:
```python
{"type": "static_select", "placeholder": {"type": "plain_text", "text": "Choose..."},
 "action_id": "pick", "options": [
    {"text": {"type": "plain_text", "text": "Option A"}, "value": "a"}
]}
```

**Multi-select** — same as select but allows multiple: `"type": "multi_static_select"`

**Date picker**: `{"type": "datepicker", "action_id": "date", "initial_date": "2026-03-16"}`

**Time picker**: `{"type": "timepicker", "action_id": "time", "initial_time": "14:30"}`

**Datetime picker**: `{"type": "datetimepicker", "action_id": "dt", "initial_date_time": 1710590400}`

**Checkboxes**:
```python
{"type": "checkboxes", "action_id": "checks", "options": [
    {"text": {"type": "mrkdwn", "text": "*Tests passing*"}, "value": "tests", "description": {"type": "plain_text", "text": "All CI green"}},
    {"text": {"type": "mrkdwn", "text": "*Code reviewed*"}, "value": "review"}
], "initial_options": [{"text": {"type": "mrkdwn", "text": "*Tests passing*"}, "value": "tests"}]}
```

**Radio buttons**:
```python
{"type": "radio_buttons", "action_id": "severity", "options": [
    {"text": {"type": "plain_text", "text": ":red_circle: Critical"}, "value": "critical"},
    {"text": {"type": "plain_text", "text": ":large_orange_circle: High"}, "value": "high"},
    {"text": {"type": "plain_text", "text": ":large_yellow_circle: Medium"}, "value": "medium"}
]}
```

### Composition objects

**Text objects**: `{"type": "plain_text", "text": "...", "emoji": true}` or `{"type": "mrkdwn", "text": "...", "verbatim": false}`

**Confirmation dialog** — attach to any interactive element via `"confirm"` prop:
```python
{"title": {"type": "plain_text", "text": "Confirm"},
 "text": {"type": "mrkdwn", "text": "Are you sure you want to *delete* this?"},
 "confirm": {"type": "plain_text", "text": "Delete"},
 "deny": {"type": "plain_text", "text": "Cancel"},
 "style": "danger"}
```

**Option object**: `{"text": {"type": "plain_text", "text": "..."}, "value": "...", "description": {"type": "plain_text", "text": "..."}}`

**Option group**: `{"label": {"type": "plain_text", "text": "Group"}, "options": [...]}`

### Mrkdwn quick reference
- `*bold*` `_italic_` `~strikethrough~` `` `inline code` ``
- `> blockquote`
- ` ```code block``` `
- `<https://url.com|Link Text>` — hyperlink
- `<@U01ABC>` — mention user, `<#C01ABC>` — mention channel
- `<!here>` `<!channel>` `<!everyone>` — broadcast mentions
- `:emoji_name:` — emoji
- Newlines: `\n`
- Lists: `• ` or `1. ` with newlines

### Date format tokens (for rich_text date elements)
`{date_num}` `{date_slash}` `{date_long}` `{date_long_full}` `{date_long_pretty}` `{date}` `{date_pretty}` `{date_short}` `{date_short_pretty}` `{time}` `{time_secs}` `{ago}` `{day_divider_pretty}`

### Design guidelines — make messages visually rich
- Use **header** to establish hierarchy
- Use **section fields** for key-value metadata grids (2 columns)
- Use **context** for timestamps, authors, source info (small grey text)
- Use **dividers** to separate logical groups
- Use **rich_text** with bold/emoji/links for formatted body content
- Use **rich_text_list** for bullet/numbered items instead of mrkdwn bullets
- Use **rich_text_preformatted** with `language` for syntax-highlighted code
- Use **rich_text_quote** for quoting messages or people
- Use **table** for structured data (tasks, comparisons, reports)
- Use **markdown** block for LLM-generated content that needs rendering
- Use **actions** with styled buttons and selects for CTAs
- Use **confirmation dialogs** on destructive actions
- Combine emoji (:red_circle: :white_check_mark: :rocket: :warning:) with text for visual scanning
- Use `<url|text>` links in mrkdwn to make items clickable
- Use user mentions `<@UID>` and channel mentions `<#CID>` for context
- **Always capture `channel` and `ts`** from `chat_postMessage` results — return them so you can later update the message with `chat_update(channel, ts, blocks=..., text=...)`. This enables iterative refinement, live dashboards, and edits without sending new messages
- When updating, rebuild the full blocks array — `chat_update` replaces the entire message, not just parts of it

### Example: rich task dashboard with table + rich text
```python
blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": ":bar_chart: Task Dashboard — March 16"}},
    {"type": "section", "fields": [
        {"type": "mrkdwn", "text": "*Open Tasks:*\n15"},
        {"type": "mrkdwn", "text": "*In Progress:*\n3"},
        {"type": "mrkdwn", "text": "*Urgent:*\n:red_circle: 4"},
        {"type": "mrkdwn", "text": "*Due This Week:*\n6"}
    ]},
    {"type": "divider"},
    {"type": "rich_text", "elements": [
        {"type": "rich_text_section", "elements": [
            {"type": "emoji", "name": "hammer_and_wrench"},
            {"type": "text", "text": " In Progress", "style": {"bold": True}}
        ]},
        {"type": "rich_text_list", "style": "bullet", "elements": [
            {"type": "rich_text_section", "elements": [
                {"type": "link", "url": "https://app.clickup.com/t/86d29u399", "text": "SF CLI Org Restrictions"},
                {"type": "text", "text": " — "},
                {"type": "text", "text": "High", "style": {"bold": True}},
                {"type": "text", "text": ", due Mar 12"}
            ]},
            {"type": "rich_text_section", "elements": [
                {"type": "link", "url": "https://app.clickup.com/t/86d280j3u", "text": "Replace Pritunl VPN with NetBird"},
                {"type": "text", "text": " — "},
                {"type": "text", "text": "High", "style": {"bold": True}},
                {"type": "text", "text": ", overdue"}
            ]}
        ]}
    ]},
    {"type": "divider"},
    {"type": "rich_text", "elements": [
        {"type": "rich_text_section", "elements": [
            {"type": "emoji", "name": "dart"},
            {"type": "text", "text": " Prioritised", "style": {"bold": True}}
        ]},
        {"type": "rich_text_list", "style": "ordered", "elements": [
            {"type": "rich_text_section", "elements": [
                {"type": "text", "text": ":red_circle: "},
                {"type": "link", "url": "https://app.clickup.com/t/86d29ndmd", "text": "Agent PIP install failure"},
                {"type": "text", "text": " — URGENT, due Mar 12"}
            ]},
            {"type": "rich_text_section", "elements": [
                {"type": "link", "url": "https://app.clickup.com/t/86d1k7501", "text": "Deploy SF AE web app"},
                {"type": "text", "text": " — due Mar 17"}
            ]}
        ]}
    ]},
    {"type": "divider"},
    {"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Source: ClickUp | <@U01EXAMPLE> | March 16, 2026"}
    ]}
]
result = slack.chat_postMessage(channel="D_SELF", text="Task Dashboard", blocks=blocks)
return f"Sent (ts: {result['ts']})"
```

### Example: incident alert with confirmation
```python
blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": ":rotating_light: Incident — API Latency Spike"}},
    {"type": "section", "text": {"type": "mrkdwn", "text": "*Service:* api-server\n*Region:* ap-south-1\n*P99 Latency:* 4.2s (threshold: 1s)\n*Started:* 14:22 IST"},
     "accessory": {"type": "image", "image_url": "https://charts.example.com/latency-spike.png", "alt_text": "Latency graph"}},
    {"type": "divider"},
    {"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": ":eyes: Acknowledge"}, "style": "primary", "action_id": "ack"},
        {"type": "button", "text": {"type": "plain_text", "text": ":ambulance: Escalate"}, "style": "danger", "action_id": "escalate",
         "confirm": {"title": {"type": "plain_text", "text": "Escalate?"}, "text": {"type": "mrkdwn", "text": "This will page the on-call team."}, "confirm": {"type": "plain_text", "text": "Escalate"}, "deny": {"type": "plain_text", "text": "Cancel"}, "style": "danger"}},
        {"type": "button", "text": {"type": "plain_text", "text": ":grafana: Dashboard"}, "url": "https://grafana.internal/d/api-latency"}
    ]},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Alert source: CloudWatch"}]}
]
```

### Example: standup with rich text quote
```python
blocks = [
    {"type": "header", "text": {"type": "plain_text", "text": ":clipboard: Daily Standup — March 16"}},
    {"type": "rich_text", "elements": [
        {"type": "rich_text_section", "elements": [{"type": "text", "text": "Yesterday", "style": {"bold": True}}]},
        {"type": "rich_text_list", "style": "bullet", "elements": [
            {"type": "rich_text_section", "elements": [{"type": "text", "text": "Shipped auth middleware rewrite"}]},
            {"type": "rich_text_section", "elements": [{"type": "text", "text": "Fixed pagination bug in /users endpoint"}]}
        ]},
        {"type": "rich_text_section", "elements": [{"type": "text", "text": "\nToday", "style": {"bold": True}}]},
        {"type": "rich_text_list", "style": "bullet", "elements": [
            {"type": "rich_text_section", "elements": [{"type": "text", "text": "Code review for open PR"}]},
            {"type": "rich_text_section", "elements": [
                {"type": "text", "text": "Build "},
                {"type": "text", "text": "Slack plugin", "style": {"code": True}},
                {"type": "text", "text": " Slack plugin for Claude Code"}
            ]}
        ]},
        {"type": "rich_text_section", "elements": [{"type": "text", "text": "\nBlockers", "style": {"bold": True}}]},
        {"type": "rich_text_list", "style": "bullet", "elements": [
            {"type": "rich_text_section", "elements": [{"type": "text", "text": "None "}, {"type": "emoji", "name": "tada"}]}
        ]}
    ]},
    {"type": "divider"},
    {"type": "rich_text", "elements": [
        {"type": "rich_text_quote", "elements": [
            {"type": "text", "text": "Two more AE groups are asking for the same presentation — it's resonating", "style": {"italic": True}},
            {"type": "text", "text": "\n— "},
            {"type": "user", "user_id": "U02EXAMPLE"}
        ]}
    ]},
    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Updated: March 16, 2026"}]}
]
```

## Error handling

Helpers raise exceptions instead of returning error dicts — catch them if needed:

```python
try:
    ts = send("#no-such-channel", "test")
    return f"Sent (ts: {ts})"
except SlackerError as e:
    return f"Resolution failed: {e}"
except SlackApiError as e:
    return f"API error: {e.response['error']}"
```

## Tips
- Channel IDs (like `C01ABCDEF`) are more reliable than names
- Use `conversations_list` to discover channel IDs first
- Thread replies need both `channel` and `thread_ts`
- Search APIs require a **user token** (`slack_user`), not a bot token
- Use `limit` parameter aggressively to reduce payload size
- Always `return` — prefer strings over dicts for lean output
