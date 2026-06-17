"""Python SDK for building quorum chat bots.

See :mod:`quorum_bot.bot` for the main entry point, :class:`Bot`.
"""

from .bot import Bot, Command, HandlerFunc, Message, MessageHandler, User
from .client import (
    ChannelMessageEvent,
    Client,
    ConnState,
    ConnStateEvent,
    ResyncEvent,
)

__all__ = [
    "Bot",
    "Command",
    "Message",
    "User",
    "HandlerFunc",
    "MessageHandler",
    # lower-level client + events, for advanced use
    "Client",
    "ConnState",
    "ConnStateEvent",
    "ResyncEvent",
    "ChannelMessageEvent",
]

__version__ = "0.1.0"
