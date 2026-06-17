"""Shared client core for the quorum bot SDK.

This is the Python counterpart of the Go ``internal/client`` package, scoped to
what a token-authenticated bot needs: TLS dialing, attaching the bot's bearer
token to every RPC, the ``Subscribe`` event pump with reconnect/backoff, and
thin wrappers around the channel RPCs. The end-to-end-encrypted DM machinery
that the Go client also carries is intentionally omitted: bots operate on group
channels only and never establish E2EE sessions.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple

import grpc

from quorum.v1 import (
    auth_pb2,
    auth_pb2_grpc,
    chat_pb2,
    chat_pb2_grpc,
)


class ConnState(Enum):
    """Connection lifecycle reported through :meth:`Client.run`."""

    ONLINE = "online"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"

    def __str__(self) -> str:  # parity with Go's ConnState.String()
        return self.value


@dataclass
class ConnStateEvent:
    state: ConnState
    err: Optional[Exception] = None


@dataclass
class ResyncEvent:
    """Fires after (re)subscribing: re-register commands, refetch state."""


@dataclass
class ChannelMessageEvent:
    msg: chat_pb2.ChannelMessage


# Event is anything delivered through Run's callback.
Event = object
EventHandler = Callable[[Event], None]


class _TokenAuth(grpc.AuthMetadataPlugin):
    """Attaches ``authorization: Bearer <token>`` to every call, mirroring the
    Go unary/stream auth interceptors. The token is read lazily so a rotated
    token (via :meth:`Client.set_token`) takes effect on the next RPC."""

    def __init__(self, token_getter: Callable[[], str]):
        self._token_getter = token_getter

    def __call__(self, context, callback):
        token = self._token_getter()
        metadata = (("authorization", f"Bearer {token}"),) if token else ()
        callback(metadata, None)


class Client:
    """A connected, token-authenticated quorum client."""

    def __init__(
        self,
        addr: str,
        ca_file: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._addr = addr
        self._logger = logger or logging.getLogger("quorum.client")

        self._token = ""
        self._token_lock = threading.Lock()
        self._user_id = ""
        self._username = ""

        self._stop = threading.Event()
        self._stream = None  # active Subscribe stream, for cancellation

        if ca_file:
            with open(ca_file, "rb") as f:
                ssl_creds = grpc.ssl_channel_credentials(root_certificates=f.read())
        else:
            ssl_creds = grpc.ssl_channel_credentials()
        call_creds = grpc.metadata_call_credentials(_TokenAuth(self._get_token))
        creds = grpc.composite_channel_credentials(ssl_creds, call_creds)

        self._channel = grpc.secure_channel(addr, creds)
        self._authc = auth_pb2_grpc.AuthServiceStub(self._channel)
        self._chatc = chat_pb2_grpc.ChatServiceStub(self._channel)

    # --- token / identity ---------------------------------------------------

    def _get_token(self) -> str:
        with self._token_lock:
            return self._token

    def set_token(self, token: str) -> None:
        """Install a pre-issued bearer token (bot tokens) instead of login."""
        with self._token_lock:
            self._token = token

    def user_id(self) -> str:
        return self._user_id

    def username(self) -> str:
        return self._username

    def who_am_i(self) -> Tuple[str, str, str]:
        """Resolve and cache the caller's identity from the current token.
        Token-authenticated clients (bots) call this in place of login."""
        resp = self._authc.WhoAmI(auth_pb2.WhoAmIRequest())
        self._user_id = resp.user_id
        self._username = resp.username
        return resp.user_id, resp.username, resp.role

    # --- channel operations (thin RPC wrappers) -----------------------------

    def list_channels(self) -> List[chat_pb2.Channel]:
        return list(self._chatc.ListChannels(chat_pb2.ListChannelsRequest()).channels)

    def list_users(self) -> List[chat_pb2.User]:
        return list(self._chatc.ListUsers(chat_pb2.ListUsersRequest()).users)

    def create_channel(self, name: str) -> chat_pb2.Channel:
        return self._chatc.CreateChannel(chat_pb2.CreateChannelRequest(name=name))

    def join_channel(self, channel_id: str) -> chat_pb2.Channel:
        return self._chatc.JoinChannel(
            chat_pb2.JoinChannelRequest(channel_id=channel_id)
        ).channel

    def leave_channel(self, channel_id: str) -> None:
        self._chatc.LeaveChannel(chat_pb2.LeaveChannelRequest(channel_id=channel_id))

    def send_channel_message(self, channel_id: str, body: str) -> None:
        self._chatc.SendChannelMessage(
            chat_pb2.SendChannelMessageRequest(channel_id=channel_id, body=body)
        )

    def channel_history(
        self, channel_id: str, before_id: int = 0, limit: int = 0
    ) -> List[chat_pb2.ChannelMessage]:
        resp = self._chatc.GetChannelHistory(
            chat_pb2.GetChannelHistoryRequest(
                channel_id=channel_id, before_id=before_id, limit=limit
            )
        )
        return list(resp.messages)

    def search_channel_messages(
        self, channel_id: str, query: str, limit: int = 0
    ) -> List[chat_pb2.ChannelMessage]:
        resp = self._chatc.SearchChannelMessages(
            chat_pb2.SearchChannelMessagesRequest(
                channel_id=channel_id, query=query, limit=limit
            )
        )
        return list(resp.messages)

    def register_commands(self, commands: List[chat_pb2.CommandSpec]) -> List[str]:
        """Declare slash commands; returns names already claimed by another bot."""
        resp = self._chatc.RegisterCommands(
            chat_pb2.RegisterCommandsRequest(commands=commands)
        )
        return list(resp.duplicate_names)

    # --- event pump ---------------------------------------------------------

    def run(self, on_event: EventHandler) -> None:
        """Pump the Subscribe stream, reconnecting with backoff until
        :meth:`close` is called. Blocks the calling thread.

        A bot has no password to re-login with, so an Unauthenticated stream
        (e.g. a revoked token) is reported as OFFLINE and retried with backoff,
        mirroring the Go client's behavior when no stored credentials exist.
        """
        backoff = 1.0
        first = True
        while not self._stop.is_set():
            if not first:
                on_event(ConnStateEvent(ConnState.RECONNECTING))
                if self._stop.wait(backoff):
                    return
                backoff = min(backoff * 2, 30.0)
            first = False

            stream = self._chatc.Subscribe(chat_pb2.SubscribeRequest())
            self._stream = stream
            on_event(ConnStateEvent(ConnState.ONLINE))
            on_event(ResyncEvent())
            backoff = 1.0

            try:
                for ev in stream:
                    if self._stop.is_set():
                        break
                    self._dispatch(ev, on_event)
            except grpc.RpcError as e:
                if self._stop.is_set():
                    return
                on_event(ConnStateEvent(ConnState.OFFLINE, e))
                continue
            finally:
                self._stream = None

    def _dispatch(self, ev: chat_pb2.ServerEvent, on_event: EventHandler) -> None:
        which = ev.WhichOneof("event")
        if which == "channel_message":
            on_event(ChannelMessageEvent(ev.channel_message))
        # presence / channel_event / system / direct_envelope are not surfaced
        # to bots (they operate on group channels only).

    def close(self) -> None:
        """Stop the event pump and tear down the connection."""
        self._stop.set()
        stream = self._stream
        if stream is not None:
            stream.cancel()
        self._channel.close()
