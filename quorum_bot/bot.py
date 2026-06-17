"""The quorum bot SDK (Python).

Bots are ordinary chat clients that authenticate with a bot token (created in
the admin TUI), join channels, and respond to slash commands. This is the
Python counterpart of the Go ``sdk/bot`` package and exposes the same surface.

Minimal bot::

    import os
    from quorum_bot import Bot

    bot = Bot("chat.example.com:8443", os.environ["QUORUM_BOT_TOKEN"])

    @bot.command("ping", "replies with pong")
    def ping(c):
        c.reply("pong")

    bot.join_channel("general")
    bot.run()  # blocks until close() / Ctrl-C

Command routing is client-side: the bot sees every message in channels it has
joined, and the SDK dispatches messages of the form ``/name args`` to the
matching registered handler. Commands are also registered with the server so
its built-in ``/commands`` listing can advertise them.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import grpc

from quorum.v1 import chat_pb2

from .client import (
    ChannelMessageEvent,
    Client,
    ConnStateEvent,
    ResyncEvent,
)


@dataclass(frozen=True)
class User:
    """Identifies a message sender."""

    id: str
    username: str


class Message:
    """A channel message as seen by the bot."""

    def __init__(self, channel_id: str, sender: User, text: str, bot: "Bot"):
        self.channel_id = channel_id
        self.sender = sender
        self.text = text
        self._bot = bot

    def reply(self, text: str) -> None:
        """Send text to the channel the message arrived in."""
        self._bot.send(self.channel_id, text)


class Command:
    """A parsed slash command addressed to one of the bot's handlers."""

    def __init__(
        self,
        name: str,
        raw_args: str,
        args: List[str],
        channel_id: str,
        sender: User,
        bot: "Bot",
    ):
        self.name = name  # without the leading slash
        self.raw_args = raw_args  # everything after the command word
        self.args = args  # raw_args split on whitespace
        self.channel_id = channel_id
        self.sender = sender
        self._bot = bot

    def reply(self, text: str) -> None:
        """Send text to the channel the command was issued in."""
        self._bot.send(self.channel_id, text)

    def replyf(self, fmt: str, *args: object) -> None:
        """``reply`` with printf-style formatting (``c.replyf("%s won", name)``)."""
        self.reply(fmt % args if args else fmt)


# A command handler is called with the parsed Command; raise to signal failure.
HandlerFunc = Callable[[Command], None]
# A message handler is called for every channel message the bot sees.
MessageHandler = Callable[[Message], None]


@dataclass
class _Registered:
    help: str
    handler: HandlerFunc


class Bot:
    """A connected quorum bot.

    Construct it, register commands with :meth:`command` (or :meth:`on_message`),
    :meth:`join_channel`, then :meth:`run`.
    """

    def __init__(
        self,
        server_addr: str,
        token: str,
        *,
        ca_file: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Dial the server and prepare a bot authenticated by ``token``.

        ``token`` must start with ``qbot_`` (created in the admin TUI); anything
        else is rejected immediately. Dialing verifies TLS but does not yet
        validate the token - that happens in :meth:`run`.

        :param ca_file: trust a private CA (e.g. the dev CA from
            ``quorum-gencert``); without it, system roots are used.
        :param logger: replace the default ``quorum.bot`` logger.
        """
        if not token.startswith("qbot_"):
            raise ValueError(
                "bot: token must be a qbot_ token (create one in the admin TUI)"
            )
        self._logger = logger or logging.getLogger("quorum.bot")
        self._client = Client(server_addr, ca_file=ca_file, logger=self._logger)
        self._client.set_token(token)

        self._lock = threading.Lock()
        self._commands: Dict[str, _Registered] = {}
        self._on_message: Optional[MessageHandler] = None

    # --- registration -------------------------------------------------------

    def command(
        self, name: str, help: str, handler: Optional[HandlerFunc] = None
    ):
        """Register a slash-command handler.

        ``name`` is matched without the leading slash, case-insensitively.
        Usable directly (``bot.command("ping", "...", fn)``) or as a decorator::

            @bot.command("ping", "replies with pong")
            def ping(c):
                c.reply("pong")
        """
        key = (name[1:] if name.startswith("/") else name).lower()

        def register(h: HandlerFunc) -> HandlerFunc:
            with self._lock:
                self._commands[key] = _Registered(help=help, handler=h)
            return h

        if handler is not None:
            register(handler)
            return None
        return register

    def on_message(self, handler: Optional[MessageHandler] = None):
        """Register a handler for every channel message the bot sees (including
        non-commands). Optional. Usable directly or as a decorator."""

        def register(h: MessageHandler) -> MessageHandler:
            with self._lock:
                self._on_message = h
            return h

        if handler is not None:
            return register(handler)
        return register

    # --- channel operations -------------------------------------------------

    def join_channel(self, name: str) -> None:
        """Join (creating if necessary) the named channel. A leading ``#`` is
        stripped. Call before :meth:`run`, or any time after."""
        name = name[1:] if name.startswith("#") else name
        for ch in self._client.list_channels():
            if ch.name.lower() == name.lower():
                self._client.join_channel(ch.id)
                return
        self._client.create_channel(name)

    def send(self, channel_id: str, text: str) -> None:
        """Post text to a channel by ID."""
        self._client.send_channel_message(channel_id, text)

    # --- lifecycle ----------------------------------------------------------

    def run(self) -> None:
        """Connect the event stream and dispatch handlers until :meth:`close`
        (or Ctrl-C). It first validates the token with WhoAmI, then re-registers
        commands after every (re)connect and recovers from handler exceptions.
        Blocks the calling thread."""
        try:
            self._client.who_am_i()
        except grpc.RpcError as e:
            raise RuntimeError(f"bot: token rejected: {e}") from e
        try:
            self._client.run(self._on_event)
        except KeyboardInterrupt:
            self.close()

    def close(self) -> None:
        """Tear down the connection and stop :meth:`run`."""
        self._client.close()

    # --- internals ----------------------------------------------------------

    def _on_event(self, ev) -> None:
        if isinstance(ev, ConnStateEvent):
            self._logger.info("connection state: %s (err=%s)", ev.state, ev.err)
        elif isinstance(ev, ResyncEvent):
            self._go(self._register_commands)
        elif isinstance(ev, ChannelMessageEvent):
            self._go(self._handle_message, ev.msg)

    @staticmethod
    def _go(fn: Callable, *args) -> None:
        """Dispatch in its own daemon thread, mirroring Go's per-message
        goroutines so a slow handler never stalls the event pump."""
        threading.Thread(target=fn, args=args, daemon=True).start()

    def _register_commands(self) -> None:
        with self._lock:
            specs = [
                chat_pb2.CommandSpec(name=name, help=c.help)
                for name, c in self._commands.items()
            ]
        if not specs:
            return
        try:
            dupes = self._client.register_commands(specs)
        except grpc.RpcError as e:
            self._logger.warning("command registration failed: %s", e)
            return
        if dupes:
            self._logger.warning(
                "commands already claimed by another bot: %s", dupes
            )

    def _handle_message(self, msg: chat_pb2.ChannelMessage) -> None:
        # Never react to our own messages (loop protection).
        if msg.sender_id == self._client.user_id():
            return

        # Panic recovery: a failing handler must not crash the bot.
        try:
            text = msg.body
            sender = User(id=msg.sender_id, username=msg.sender_name)

            with self._lock:
                on_message = self._on_message
            if on_message is not None:
                on_message(Message(msg.channel_id, sender, text, self))

            if not text.startswith("/"):
                return
            fields = text.split()
            first = fields[0]
            name = (first[1:] if first.startswith("/") else first).lower()
            with self._lock:
                cmd = self._commands.get(name)
            if cmd is None:
                return

            raw_args = text[len(first):].strip()
            c = Command(
                name=name,
                raw_args=raw_args,
                args=fields[1:],
                channel_id=msg.channel_id,
                sender=sender,
                bot=self,
            )
            try:
                cmd.handler(c)
            except Exception as e:  # handler-level failure → friendly reply
                self._logger.error("command failed: command=%s err=%s", name, e)
                try:
                    c.reply(f"⚠ command failed: {e}")
                except Exception:
                    pass
        except Exception:
            self._logger.exception("handler panic")
