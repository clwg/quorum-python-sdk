#!/usr/bin/env python3
"""dicebot is an example quorum bot: /roll NdS rolls dice.

Usage::

    export QUORUM_BOT_TOKEN=qbot_...   # from the admin TUI ([2] Bots -> a)
    python examples/dicebot.py --addr localhost:8443 --ca certs/ca.pem --channel general
    # in a chat client:  /roll 2d6
"""

import argparse
import logging
import os
import random
import sys

from quorum_bot import Bot


def parse_dice(s: str):
    """Parse "NdS" (both parts optional: "" -> 1d6, "3" -> 3d6)."""
    n, sides = 1, 6
    s = s.strip().lower()
    if not s:
        return n, sides
    num_str, _, side_str = s.partition("d")
    if num_str:
        if not num_str.isdigit() or not (1 <= int(num_str) <= 100):
            raise ValueError(f"bad dice count {num_str!r}")
        n = int(num_str)
    if side_str:
        if not side_str.isdigit() or not (2 <= int(side_str) <= 1000):
            raise ValueError(f"bad die size {side_str!r}")
        sides = int(side_str)
    return n, sides


def main() -> None:
    ap = argparse.ArgumentParser(description="quorum dicebot")
    ap.add_argument("--addr", default="localhost:8443", help="server address")
    ap.add_argument("--ca", default=None, help="CA certificate (default: system roots)")
    ap.add_argument("--channel", default="general", help="channel to join")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    token = os.environ.get("QUORUM_BOT_TOKEN")
    if not token:
        sys.exit("set QUORUM_BOT_TOKEN (create a bot in the admin TUI)")

    bot = Bot(args.addr, token, ca_file=args.ca)

    @bot.command("roll", "roll dice, e.g. /roll 2d6")
    def roll(c):
        try:
            n, sides = parse_dice(c.raw_args)
        except ValueError as e:
            c.replyf("%s - usage: /roll NdS (e.g. 2d6)", e)
            return
        total = sum(random.randint(1, sides) for _ in range(n))
        c.replyf("%s rolled %d 🎲 (%dd%d)", c.sender.username, total, n, sides)

    bot.join_channel(args.channel)
    logging.info("dicebot up in #%s", args.channel)
    bot.run()


if __name__ == "__main__":
    main()
