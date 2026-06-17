#!/usr/bin/env python3
"""claude_assistant is a feature-rich Quorum bot built on the **official Claude
Agent SDK** (``claude-agent-sdk``) rather than shelling out to ``claude -p``.

Unlike ``claudebot.py`` (a one-shot wrapper around the CLI), this bot:

* keeps **per-channel conversation context** so follow-up questions just work
  (it resumes the channel's Agent SDK session and feeds Claude the messages
  posted since it last replied);
* gives Claude **tools** to search and read the channel's history, list members,
  and (optionally) search the web / fetch URLs - so it can answer questions that
  depend on what was actually said in the channel or on current facts;
* exposes several slash commands beyond plain Q&A.

Commands
--------
    /ask <question>     ask Claude; remembers the channel (alias: /claude)
    /summarize [N]      summarize the last N messages (default 60)
    /find <keywords>    search this channel's message history (no LLM, instant)
    /reset              forget this channel's conversation context
    /about              list these commands

(``/search`` and ``/help`` are reserved by the chat client - it handles them
locally, so they never reach a bot. Hence ``/find`` and ``/about`` here.)

How the channel tools work
--------------------------
Claude's channel tools are thin wrappers over the bot SDK's existing read-only
RPCs (``Client.channel_history`` / ``search_channel_messages`` / ``list_users``
/ ``list_channels``). No protobuf changes are needed - they're already part of
the contract; we just surface them to the model as an in-process MCP server.

Requirements
------------
* ``pip install quorum-bot claude-agent-sdk``
* the ``claude`` CLI installed and authenticated on this machine (it backs the
  Agent SDK; e.g. a prior ``claude login`` or ``ANTHROPIC_API_KEY`` in the env,
  which the bot inherits).

Usage
-----
    export QUORUM_BOT_TOKEN=qbot_...   # from the admin TUI ([2] Bots -> a)
    python examples/claude_assistant.py --addr localhost:8443 --ca certs/ca.pem --channel general
    # in a chat client:  /ask what did we decide about the deploy window?
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from quorum_bot import Bot

# The Agent SDK is an optional dependency; import lazily so the module still
# loads (and main() can print a friendly install hint) when it's missing.
try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolUseBlock,
        create_sdk_mcp_server,
        query,
        tool,
    )

    _SDK_OK = True
    _SDK_ERR: Optional[Exception] = None
except Exception as e:  # pragma: no cover - exercised only without the SDK
    _SDK_OK = False
    _SDK_ERR = e

# Tool annotations are nice-to-have (readOnlyHint lets Claude batch read-only
# tool calls in parallel) but newer than the rest of the API; degrade if absent.
try:
    from claude_agent_sdk import ToolAnnotations
except Exception:  # pragma: no cover
    ToolAnnotations = None  # type: ignore[assignment]

# Server caps messages at 4096 bytes; leave headroom for the "[i/n] " prefix.
MAX_CHUNK = 3900
# Default count for /summarize and the per-ask channel-context window.
DEFAULT_SUMMARY = 60
DEFAULT_HISTORY = 25
# Bound a channel session's growth (cost/latency): start fresh after this many
# /ask turns. This is the "within reason" part of "maintain channel context".
MAX_SESSION_TURNS = 40

HELP_TEXT = (
    "🤖 I'm a Claude-powered assistant. I remember this channel's conversation "
    "and can search it.\n"
    "• /ask <question> - ask me anything (I recall the channel; alias /claude)\n"
    "• /summarize [N] - recap the last N messages (default 60)\n"
    "• /find <keywords> - find past messages in this channel\n"
    "• /reset - make me forget this channel's context\n"
    "• /about - this message"
)


# --- formatting helpers -----------------------------------------------------


def chunk(s: str, max_len: int) -> List[str]:
    """Split s into pieces of at most max_len chars, preferring a newline break."""
    chunks: List[str] = []
    while len(s) > max_len:
        cut = max_len
        nl = s.rfind("\n", 0, cut)
        if nl > max_len // 2:
            cut = nl + 1  # keep the newline with this chunk
        chunks.append(s[:cut])
        s = s[cut:]
    if s:
        chunks.append(s)
    return chunks


def reply_chunks(c, text: str) -> None:
    """Reply with text, split across messages to stay under the server's limit."""
    parts = chunk(text, MAX_CHUNK)
    for i, part in enumerate(parts, 1):
        if len(parts) > 1:
            part = f"[{i}/{len(parts)}] {part}"
        c.reply(part)


def _format_msgs(msgs, *, max_body: int = 300) -> str:
    """Render channel messages as a compact ``name: body`` transcript."""
    lines = []
    for m in msgs:
        body = " ".join(m.body.split())  # collapse whitespace/newlines
        if len(body) > max_body:
            body = body[: max_body - 1] + "…"
        lines.append(f"{m.sender_name}: {body}")
    return "\n".join(lines)


def _short(obj: Any, n: int = 120) -> str:
    s = repr(obj)
    return s if len(s) <= n else s[: n - 1] + "…"


# --- per-channel state ------------------------------------------------------


@dataclass
class _ChannelState:
    session_id: Optional[str] = None  # Agent SDK session to resume for continuity
    last_seen_id: int = 0  # highest message id already shown to Claude
    turns: int = 0  # /ask turns on the current session (for auto-reset)


# --- the assistant ----------------------------------------------------------


class Assistant:
    """Bridges the threaded bot SDK to the async Claude Agent SDK and holds the
    per-channel conversation state.

    The bot dispatches each command on its own thread, so each call runs its own
    asyncio loop via :func:`asyncio.run`. A per-channel lock serializes ``/ask``
    calls in the same channel, keeping the resumed session coherent (you can't
    resume a session that's still in flight).
    """

    def __init__(
        self,
        bot: Bot,
        *,
        model: Optional[str],
        timeout: float,
        max_turns: int,
        max_cost: Optional[float],
        allow_web: bool,
        history_context: int,
        logger: logging.Logger,
    ):
        self._bot = bot
        # The bot's underlying client exposes the read-only RPC wrappers we need.
        self._client = bot._client
        self._model = model
        self._timeout = timeout
        self._max_turns = max_turns
        self._max_cost = max_cost
        self._allow_web = allow_web
        self._history_context = history_context
        self._logger = logger

        import threading

        self._meta_lock = threading.Lock()
        self._locks: dict = {}
        self._channels: dict = {}
        self._channel_names: dict = {}

    # --- public, thread-side entry points -----------------------------------

    def ask(self, channel_id: str, username: str, question: str) -> str:
        """Answer ``question`` with channel context; blocks. Raises RuntimeError
        on timeout or empty output."""
        with self._lock_for(channel_id):
            return self._run(self._answer(channel_id, username, question))

    def summarize(self, channel_id: str, n: int) -> str:
        """Summarize the last ``n`` messages of the channel; blocks."""
        return self._run(self._summarize(channel_id, n))

    def reset(self, channel_id: str) -> None:
        with self._meta_lock:
            self._channels.pop(channel_id, None)

    def _run(self, coro):
        try:
            return asyncio.run(asyncio.wait_for(coro, self._timeout))
        except asyncio.TimeoutError:
            raise RuntimeError(f"timed out after {self._timeout:g}s")

    # --- locks / state ------------------------------------------------------

    def _lock_for(self, channel_id: str):
        import threading

        with self._meta_lock:
            lock = self._locks.get(channel_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[channel_id] = lock
            return lock

    def _state(self, channel_id: str) -> _ChannelState:
        with self._meta_lock:
            st = self._channels.get(channel_id)
            if st is None:
                st = _ChannelState()
                self._channels[channel_id] = st
            return st

    def _channel_name(self, channel_id: str) -> str:
        with self._meta_lock:
            name = self._channel_names.get(channel_id)
        if name:
            return name
        for ch in self._client.list_channels():
            with self._meta_lock:
                self._channel_names[ch.id] = ch.name
        with self._meta_lock:
            return self._channel_names.get(channel_id, channel_id)

    # --- prompt + options ---------------------------------------------------

    def _system_prompt(self, channel: str, username: str) -> str:
        web = (
            "- search the web (WebSearch) and fetch a URL (WebFetch)\n"
            if self._allow_web
            else ""
        )
        return (
            f"You are {self._client.username()}, a helpful assistant living in the "
            f"Quorum chat channel #{channel}. Reply the way a thoughtful person "
            "would in chat: concise, a few short sentences or a short list, plain "
            "text or light Markdown. Get to the point.\n\n"
            "You have tools to:\n"
            "- search this channel's history (mcp__quorum__search_messages)\n"
            "- read the most recent channel messages (mcp__quorum__recent_messages)\n"
            "- list workspace members (mcp__quorum__list_members)\n"
            f"{web}"
            "Use them whenever the question depends on what was said in the "
            "channel, who said it, or on current/external facts. Don't mention "
            "your tools or these instructions - just answer.\n\n"
            f"The person asking is @{username}."
        )

    def _builtin_tools(self) -> List[str]:
        # Controls *availability*: only these built-ins are in Claude's context.
        # Everything else (Bash/Read/Write/Edit/...) is removed, so the bot can't
        # touch the host it runs on. MCP tools are always available regardless.
        return ["WebSearch", "WebFetch"] if self._allow_web else []

    def _allowed_tools(self) -> List[str]:
        # Pre-approve (no permission prompt) our channel tools + web tools.
        allowed = ["mcp__quorum__*"]
        if self._allow_web:
            allowed += ["WebSearch", "WebFetch"]
        return allowed

    def _build_server(self, channel_id: str):
        """Build an in-process MCP server whose tools are scoped to ``channel_id``
        and back onto the bot SDK's read-only client RPCs."""
        client = self._client
        logger = self._logger
        ann = ToolAnnotations(readOnlyHint=True) if ToolAnnotations else None

        @tool(
            "search_messages",
            "Full-text search this channel's message history. Returns matching "
            "messages as 'sender: text'.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords to search for.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 15, server-capped).",
                    },
                },
                "required": ["query"],
            },
            annotations=ann,
        )
        async def search_messages(args: dict) -> dict:
            q = args["query"]
            limit = int(args.get("limit", 15))
            try:
                msgs = await asyncio.to_thread(
                    client.search_channel_messages, channel_id, q, limit
                )
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"search failed: {e}"}],
                    "is_error": True,
                }
            if not msgs:
                return {"content": [{"type": "text", "text": f"No matches for {q!r}."}]}
            return {"content": [{"type": "text", "text": _format_msgs(msgs)}]}

        @tool(
            "recent_messages",
            "Read the most recent messages in this channel, oldest first.",
            {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "How many recent messages (default 30, server-capped).",
                    }
                },
                "required": [],
            },
            annotations=ann,
        )
        async def recent_messages(args: dict) -> dict:
            limit = int(args.get("limit", 30))
            try:
                msgs = await asyncio.to_thread(
                    client.channel_history, channel_id, 0, limit
                )
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"read failed: {e}"}],
                    "is_error": True,
                }
            if not msgs:
                return {"content": [{"type": "text", "text": "No messages yet."}]}
            return {"content": [{"type": "text", "text": _format_msgs(msgs)}]}

        @tool(
            "list_members",
            "List the workspace's users and whether each is currently online.",
            {"type": "object", "properties": {}, "required": []},
            annotations=ann,
        )
        async def list_members(args: dict) -> dict:
            try:
                users = await asyncio.to_thread(client.list_users)
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"lookup failed: {e}"}],
                    "is_error": True,
                }
            lines = [
                f"{u.username} ({'online' if u.online else 'offline'})" for u in users
            ]
            text = "\n".join(lines) if lines else "No users."
            return {"content": [{"type": "text", "text": text}]}

        logger.debug("built quorum MCP server for channel %s", channel_id)
        return create_sdk_mcp_server(
            name="quorum",
            version="1.0.0",
            tools=[search_messages, recent_messages, list_members],
        )

    # --- async cores --------------------------------------------------------

    async def _collect(self, prompt: str, options) -> Tuple[str, Optional[str], bool]:
        """Drive one query() to completion. Returns (answer, session_id, is_error).
        Prefers ResultMessage.result; falls back to concatenated text blocks."""
        text_parts: List[str] = []
        result_text: Optional[str] = None
        session_id: Optional[str] = None
        is_error = False
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_parts.append(block.text)
                    elif isinstance(block, ToolUseBlock):
                        self._logger.info("tool: %s %s", block.name, _short(block.input))
            elif isinstance(message, ResultMessage):
                session_id = message.session_id
                is_error = message.is_error
                if message.subtype == "success":
                    result_text = message.result
        answer = (result_text or "\n".join(p for p in text_parts if p)).strip()
        return answer, session_id, is_error

    async def _answer(self, channel_id: str, username: str, question: str) -> str:
        bot_uid = self._client.user_id()
        state = self._state(channel_id)

        # Bound session growth: occasionally start fresh (keeps cost/latency sane).
        if state.session_id and state.turns >= MAX_SESSION_TURNS:
            self._logger.info(
                "channel %s: auto-reset session after %d turns", channel_id, state.turns
            )
            state.session_id, state.turns = None, 0

        # Feed Claude the human messages posted since it last replied here, so it
        # has fresh channel context even on a brand-new or just-reset session.
        history = await asyncio.to_thread(
            self._client.channel_history, channel_id, 0, self._history_context
        )
        new = [
            m
            for m in history
            if m.id > state.last_seen_id
            and m.sender_id != bot_uid
            and not m.body.startswith("/")  # skip command lines (incl. this /ask)
        ]
        if history:
            state.last_seen_id = max(state.last_seen_id, max(m.id for m in history))

        channel = await asyncio.to_thread(self._channel_name, channel_id)

        parts: List[str] = []
        if new:
            parts.append("Recent messages in this channel since you last replied:")
            parts.append(_format_msgs(new[-20:]))
            parts.append("")
        parts.append(f"{username} asks: {question}")
        prompt = "\n".join(parts)

        options = ClaudeAgentOptions(
            system_prompt=self._system_prompt(channel, username),
            mcp_servers={"quorum": self._build_server(channel_id)},
            tools=self._builtin_tools(),
            allowed_tools=self._allowed_tools(),
            permission_mode="bypassPermissions",  # unattended: never block on a prompt
            max_turns=self._max_turns,
            max_budget_usd=self._max_cost,
            model=self._model,
            resume=state.session_id,
            setting_sources=None,  # don't inherit the host's settings/CLAUDE.md
        )

        answer, session_id, _ = await self._collect(prompt, options)
        if session_id:
            state.session_id = session_id
            state.turns += 1
        if not answer:
            raise RuntimeError("Claude returned no output")
        return answer

    async def _summarize(self, channel_id: str, n: int) -> str:
        msgs = await asyncio.to_thread(self._client.channel_history, channel_id, 0, n)
        convo = [m for m in msgs if not m.body.startswith("/")]
        if not convo:
            return "Nothing to summarize yet in this channel."
        transcript = _format_msgs(convo, max_body=500)
        prompt = (
            "Summarize the following channel conversation for someone catching up. "
            "Give a short bulleted list of the main topics, decisions, open "
            "questions, and any action items. Be concise and neutral.\n\n"
            f"{transcript}"
        )
        options = ClaudeAgentOptions(
            system_prompt="You write concise, neutral summaries of chat discussions.",
            tools=[],  # pure summarization, no tools needed
            permission_mode="bypassPermissions",
            max_turns=2,
            max_budget_usd=self._max_cost,
            model=self._model,
            setting_sources=None,
        )
        answer, _, _ = await self._collect(prompt, options)
        if not answer:
            raise RuntimeError("Claude returned no output")
        return answer


# --- wiring -----------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description="quorum claude-assistant bot")
    ap.add_argument("--addr", default="localhost:8443", help="server address")
    ap.add_argument("--ca", default=None, help="CA certificate (default: system roots)")
    ap.add_argument("--channel", default="general", help="channel to join")
    ap.add_argument("--model", default=None, help="model alias/name (default: CLI default)")
    ap.add_argument("--timeout", type=float, default=180.0, help="max seconds per reply")
    ap.add_argument("--max-turns", type=int, default=12, help="max agentic turns per ask")
    ap.add_argument("--max-cost", type=float, default=None, help="max USD per ask (optional)")
    ap.add_argument("--history", type=int, default=DEFAULT_HISTORY, help="channel-context window size")
    ap.add_argument("--no-web", action="store_true", help="disable web search/fetch tools")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not _SDK_OK:
        sys.exit(
            "claude-assistant needs the Claude Agent SDK and the `claude` CLI.\n"
            "  pip install claude-agent-sdk   # and: claude login (or set ANTHROPIC_API_KEY)\n"
            f"  import error: {_SDK_ERR}"
        )

    token = os.environ.get("QUORUM_BOT_TOKEN")
    if not token:
        sys.exit("set QUORUM_BOT_TOKEN (create a bot in the admin TUI)")

    bot = Bot(args.addr, token, ca_file=args.ca)
    assistant = Assistant(
        bot,
        model=args.model,
        timeout=args.timeout,
        max_turns=args.max_turns,
        max_cost=args.max_cost,
        allow_web=not args.no_web,
        history_context=args.history,
        logger=logging.getLogger("claude.assistant"),
    )

    @bot.command("ask", "ask Claude (remembers the channel); e.g. /ask what's our deploy plan?")
    def ask(c):
        q = c.raw_args.strip()
        if not q:
            c.reply("usage: /ask <question> (e.g. /ask summarize the API debate)")
            return
        c.replyf("🤔 thinking for %s…", c.sender.username)
        try:
            answer = assistant.ask(c.channel_id, c.sender.username, q)
        except RuntimeError as e:
            c.replyf("⚠ claude failed: %s", e)
            return
        reply_chunks(c, answer)

    # Alias so users coming from claudebot keep their muscle memory.
    bot.command("claude", "alias for /ask", ask)

    @bot.command("summarize", "summarize recent channel discussion; e.g. /summarize 80")
    def summarize(c):
        n = DEFAULT_SUMMARY
        if c.args:
            if not c.args[0].isdigit():
                c.reply("usage: /summarize [N]  (N = how many recent messages)")
                return
            n = max(1, min(200, int(c.args[0])))
        c.reply("📝 summarizing…")
        try:
            answer = assistant.summarize(c.channel_id, n)
        except RuntimeError as e:
            c.replyf("⚠ claude failed: %s", e)
            return
        reply_chunks(c, answer)

    # Named /find, not /search: the chat client reserves /search (and /help),
    # handling them locally so they never reach a bot.
    @bot.command("find", "search this channel's history; e.g. /find deployment plan")
    def find(c):
        q = c.raw_args.strip()
        if not q:
            c.reply("usage: /find <keywords>")
            return
        try:
            msgs = bot._client.search_channel_messages(c.channel_id, q, 10)
        except Exception as e:
            c.replyf("⚠ search failed: %s", e)
            return
        if not msgs:
            c.replyf("no messages matching %r", q)
            return
        lines = [f"🔎 {len(msgs)} match(es) for {q!r}:", _format_msgs(msgs, max_body=200)]
        reply_chunks(c, "\n".join(lines))

    @bot.command("reset", "forget this channel's conversation context")
    def reset(c):
        assistant.reset(c.channel_id)
        c.reply("🧹 cleared this channel's context - starting fresh.")

    # Named /about, not /help: /help is a reserved client command (see /find).
    @bot.command("about", "what this assistant can do")
    def about(c):
        c.reply(HELP_TEXT)

    bot.join_channel(args.channel)
    logging.info(
        "claude-assistant up in #%s (web=%s, model=%s)",
        args.channel,
        not args.no_web,
        args.model or "default",
    )
    bot.run()


if __name__ == "__main__":
    main()
