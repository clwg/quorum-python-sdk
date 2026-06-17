#!/usr/bin/env python3
"""claudebot is an example quorum bot: /claude <query> runs the Claude CLI
(``claude -p "<query>"``) and posts the answer back to the channel.

The machine running the bot must have the ``claude`` CLI installed and
authenticated (it inherits this process's environment, e.g. ANTHROPIC_API_KEY
or a prior ``claude login``).

Usage::

    export QUORUM_BOT_TOKEN=qbot_...   # from the admin TUI ([2] Bots -> a)
    python examples/claudebot.py --addr localhost:8443 --ca certs/ca.pem --channel general
    # in a chat client:  /claude explain async/await in one sentence
"""

import argparse
import logging
import os
import subprocess
import sys

from quorum_bot import Bot

# Cap each reply below the server's 4096-byte message limit, leaving headroom
# for the optional "[i/n] " part prefix on multi-message answers.
MAX_CHUNK = 3900


def run_claude(claude_bin: str, timeout: float, query: str) -> str:
    """Invoke ``claude -p "<query>"`` and return its trimmed stdout. The query
    is passed as a single argument (no shell), so it is not interpreted."""
    try:
        proc = subprocess.run(
            [claude_bin, "-p", query],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"timed out after {timeout:g}s")
    if proc.returncode != 0:
        msg = proc.stderr.strip()
        raise RuntimeError(msg or f"claude exited with status {proc.returncode}")
    out = proc.stdout.strip()
    if not out:
        raise RuntimeError("claude returned no output")
    return out


def chunk(s: str, max_len: int):
    """Split s into pieces of at most max_len chars, preferring to break on a
    newline."""
    chunks = []
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


def main() -> None:
    ap = argparse.ArgumentParser(description="quorum claudebot")
    ap.add_argument("--addr", default="localhost:8443", help="server address")
    ap.add_argument("--ca", default=None, help="CA certificate (default: system roots)")
    ap.add_argument("--channel", default="general", help="channel to join")
    ap.add_argument("--claude", default="claude", help="path to the claude CLI")
    ap.add_argument("--timeout", type=float, default=120.0, help="max seconds to wait for claude")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    token = os.environ.get("QUORUM_BOT_TOKEN")
    if not token:
        sys.exit("set QUORUM_BOT_TOKEN (create a bot in the admin TUI)")

    bot = Bot(args.addr, token, ca_file=args.ca)

    @bot.command("claude", "ask Claude, e.g. /claude explain async/await")
    def claude(c):
        query = c.raw_args.strip()
        if not query:
            c.reply("usage: /claude <query> (e.g. /claude explain async/await)")
            return
        # claude -p can take a while; let the asker know we're on it.
        c.replyf("🤔 asking Claude for %s…", c.sender.username)
        try:
            answer = run_claude(args.claude, args.timeout, query)
        except RuntimeError as e:
            # Reply directly for a friendly message instead of the SDK's
            # generic "⚠ command failed".
            c.replyf("⚠ claude failed: %s", e)
            return
        chunks = chunk(answer, MAX_CHUNK)
        for i, part in enumerate(chunks, 1):
            if len(chunks) > 1:
                part = f"[{i}/{len(chunks)}] {part}"
            c.reply(part)

    bot.join_channel(args.channel)
    logging.info("claudebot up in #%s", args.channel)
    bot.run()


if __name__ == "__main__":
    main()
