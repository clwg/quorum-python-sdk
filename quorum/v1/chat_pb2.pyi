import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SubscribeRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ServerEvent(_message.Message):
    __slots__ = ("channel_message", "direct_envelope", "presence", "channel_event", "system")
    CHANNEL_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    DIRECT_ENVELOPE_FIELD_NUMBER: _ClassVar[int]
    PRESENCE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_EVENT_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_FIELD_NUMBER: _ClassVar[int]
    channel_message: ChannelMessage
    direct_envelope: DirectEnvelope
    presence: PresenceEvent
    channel_event: ChannelEvent
    system: SystemNotice
    def __init__(self, channel_message: _Optional[_Union[ChannelMessage, _Mapping]] = ..., direct_envelope: _Optional[_Union[DirectEnvelope, _Mapping]] = ..., presence: _Optional[_Union[PresenceEvent, _Mapping]] = ..., channel_event: _Optional[_Union[ChannelEvent, _Mapping]] = ..., system: _Optional[_Union[SystemNotice, _Mapping]] = ...) -> None: ...

class Channel(_message.Message):
    __slots__ = ("id", "name", "topic", "is_member", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    IS_MEMBER_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    topic: str
    is_member: bool
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., topic: _Optional[str] = ..., is_member: _Optional[bool] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ChannelMessage(_message.Message):
    __slots__ = ("id", "channel_id", "sender_id", "sender_name", "body", "sent_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    SENDER_NAME_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    SENT_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    channel_id: str
    sender_id: str
    sender_name: str
    body: str
    sent_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[int] = ..., channel_id: _Optional[str] = ..., sender_id: _Optional[str] = ..., sender_name: _Optional[str] = ..., body: _Optional[str] = ..., sent_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class DirectEnvelope(_message.Message):
    __slots__ = ("type", "sender_id", "sender_name", "recipient_id", "session_id", "payload", "counter")
    class Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TYPE_UNSPECIFIED: _ClassVar[DirectEnvelope.Type]
        TYPE_SESSION_INIT: _ClassVar[DirectEnvelope.Type]
        TYPE_SESSION_ACCEPT: _ClassVar[DirectEnvelope.Type]
        TYPE_MESSAGE: _ClassVar[DirectEnvelope.Type]
        TYPE_SESSION_CLOSE: _ClassVar[DirectEnvelope.Type]
    TYPE_UNSPECIFIED: DirectEnvelope.Type
    TYPE_SESSION_INIT: DirectEnvelope.Type
    TYPE_SESSION_ACCEPT: DirectEnvelope.Type
    TYPE_MESSAGE: DirectEnvelope.Type
    TYPE_SESSION_CLOSE: DirectEnvelope.Type
    TYPE_FIELD_NUMBER: _ClassVar[int]
    SENDER_ID_FIELD_NUMBER: _ClassVar[int]
    SENDER_NAME_FIELD_NUMBER: _ClassVar[int]
    RECIPIENT_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    PAYLOAD_FIELD_NUMBER: _ClassVar[int]
    COUNTER_FIELD_NUMBER: _ClassVar[int]
    type: DirectEnvelope.Type
    sender_id: str
    sender_name: str
    recipient_id: str
    session_id: bytes
    payload: bytes
    counter: int
    def __init__(self, type: _Optional[_Union[DirectEnvelope.Type, str]] = ..., sender_id: _Optional[str] = ..., sender_name: _Optional[str] = ..., recipient_id: _Optional[str] = ..., session_id: _Optional[bytes] = ..., payload: _Optional[bytes] = ..., counter: _Optional[int] = ...) -> None: ...

class PresenceEvent(_message.Message):
    __slots__ = ("user_id", "username", "online")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    ONLINE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    online: bool
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., online: _Optional[bool] = ...) -> None: ...

class ChannelEvent(_message.Message):
    __slots__ = ("type", "channel", "user_id", "username")
    class Type(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        TYPE_UNSPECIFIED: _ClassVar[ChannelEvent.Type]
        TYPE_CREATED: _ClassVar[ChannelEvent.Type]
        TYPE_MEMBER_JOINED: _ClassVar[ChannelEvent.Type]
        TYPE_MEMBER_LEFT: _ClassVar[ChannelEvent.Type]
    TYPE_UNSPECIFIED: ChannelEvent.Type
    TYPE_CREATED: ChannelEvent.Type
    TYPE_MEMBER_JOINED: ChannelEvent.Type
    TYPE_MEMBER_LEFT: ChannelEvent.Type
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    type: ChannelEvent.Type
    channel: Channel
    user_id: str
    username: str
    def __init__(self, type: _Optional[_Union[ChannelEvent.Type, str]] = ..., channel: _Optional[_Union[Channel, _Mapping]] = ..., user_id: _Optional[str] = ..., username: _Optional[str] = ...) -> None: ...

class SystemNotice(_message.Message):
    __slots__ = ("text", "server_time")
    TEXT_FIELD_NUMBER: _ClassVar[int]
    SERVER_TIME_FIELD_NUMBER: _ClassVar[int]
    text: str
    server_time: _timestamp_pb2.Timestamp
    def __init__(self, text: _Optional[str] = ..., server_time: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class SendChannelMessageRequest(_message.Message):
    __slots__ = ("channel_id", "body")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    BODY_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    body: str
    def __init__(self, channel_id: _Optional[str] = ..., body: _Optional[str] = ...) -> None: ...

class SendChannelMessageResponse(_message.Message):
    __slots__ = ("message_id",)
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    message_id: int
    def __init__(self, message_id: _Optional[int] = ...) -> None: ...

class CreateChannelRequest(_message.Message):
    __slots__ = ("name", "topic")
    NAME_FIELD_NUMBER: _ClassVar[int]
    TOPIC_FIELD_NUMBER: _ClassVar[int]
    name: str
    topic: str
    def __init__(self, name: _Optional[str] = ..., topic: _Optional[str] = ...) -> None: ...

class JoinChannelRequest(_message.Message):
    __slots__ = ("channel_id",)
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    def __init__(self, channel_id: _Optional[str] = ...) -> None: ...

class JoinChannelResponse(_message.Message):
    __slots__ = ("channel",)
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    channel: Channel
    def __init__(self, channel: _Optional[_Union[Channel, _Mapping]] = ...) -> None: ...

class LeaveChannelRequest(_message.Message):
    __slots__ = ("channel_id",)
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    def __init__(self, channel_id: _Optional[str] = ...) -> None: ...

class LeaveChannelResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListChannelsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListChannelsResponse(_message.Message):
    __slots__ = ("channels",)
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedCompositeFieldContainer[Channel]
    def __init__(self, channels: _Optional[_Iterable[_Union[Channel, _Mapping]]] = ...) -> None: ...

class GetChannelHistoryRequest(_message.Message):
    __slots__ = ("channel_id", "before_id", "limit")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    BEFORE_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    before_id: int
    limit: int
    def __init__(self, channel_id: _Optional[str] = ..., before_id: _Optional[int] = ..., limit: _Optional[int] = ...) -> None: ...

class GetChannelHistoryResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[ChannelMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[ChannelMessage, _Mapping]]] = ...) -> None: ...

class SearchChannelMessagesRequest(_message.Message):
    __slots__ = ("channel_id", "query", "limit")
    CHANNEL_ID_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    channel_id: str
    query: str
    limit: int
    def __init__(self, channel_id: _Optional[str] = ..., query: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class SearchChannelMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[ChannelMessage]
    def __init__(self, messages: _Optional[_Iterable[_Union[ChannelMessage, _Mapping]]] = ...) -> None: ...

class ListUsersRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ListUsersResponse(_message.Message):
    __slots__ = ("users",)
    USERS_FIELD_NUMBER: _ClassVar[int]
    users: _containers.RepeatedCompositeFieldContainer[User]
    def __init__(self, users: _Optional[_Iterable[_Union[User, _Mapping]]] = ...) -> None: ...

class User(_message.Message):
    __slots__ = ("id", "username", "role", "online")
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    ONLINE_FIELD_NUMBER: _ClassVar[int]
    id: str
    username: str
    role: str
    online: bool
    def __init__(self, id: _Optional[str] = ..., username: _Optional[str] = ..., role: _Optional[str] = ..., online: _Optional[bool] = ...) -> None: ...

class SendDirectRequest(_message.Message):
    __slots__ = ("envelope",)
    ENVELOPE_FIELD_NUMBER: _ClassVar[int]
    envelope: DirectEnvelope
    def __init__(self, envelope: _Optional[_Union[DirectEnvelope, _Mapping]] = ...) -> None: ...

class SendDirectResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class RegisterCommandsRequest(_message.Message):
    __slots__ = ("commands",)
    COMMANDS_FIELD_NUMBER: _ClassVar[int]
    commands: _containers.RepeatedCompositeFieldContainer[CommandSpec]
    def __init__(self, commands: _Optional[_Iterable[_Union[CommandSpec, _Mapping]]] = ...) -> None: ...

class CommandSpec(_message.Message):
    __slots__ = ("name", "help")
    NAME_FIELD_NUMBER: _ClassVar[int]
    HELP_FIELD_NUMBER: _ClassVar[int]
    name: str
    help: str
    def __init__(self, name: _Optional[str] = ..., help: _Optional[str] = ...) -> None: ...

class RegisterCommandsResponse(_message.Message):
    __slots__ = ("duplicate_names",)
    DUPLICATE_NAMES_FIELD_NUMBER: _ClassVar[int]
    duplicate_names: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, duplicate_names: _Optional[_Iterable[str]] = ...) -> None: ...
