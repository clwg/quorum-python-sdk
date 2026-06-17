import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class LoginRequest(_message.Message):
    __slots__ = ("username", "password")
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    PASSWORD_FIELD_NUMBER: _ClassVar[int]
    username: str
    password: str
    def __init__(self, username: _Optional[str] = ..., password: _Optional[str] = ...) -> None: ...

class LoginResponse(_message.Message):
    __slots__ = ("token", "user_id", "username", "role", "expires_at")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    EXPIRES_AT_FIELD_NUMBER: _ClassVar[int]
    token: str
    user_id: str
    username: str
    role: str
    expires_at: _timestamp_pb2.Timestamp
    def __init__(self, token: _Optional[str] = ..., user_id: _Optional[str] = ..., username: _Optional[str] = ..., role: _Optional[str] = ..., expires_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class LogoutRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class LogoutResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ChangePasswordRequest(_message.Message):
    __slots__ = ("old_password", "new_password")
    OLD_PASSWORD_FIELD_NUMBER: _ClassVar[int]
    NEW_PASSWORD_FIELD_NUMBER: _ClassVar[int]
    old_password: str
    new_password: str
    def __init__(self, old_password: _Optional[str] = ..., new_password: _Optional[str] = ...) -> None: ...

class ChangePasswordResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WhoAmIRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class WhoAmIResponse(_message.Message):
    __slots__ = ("user_id", "username", "role")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    role: str
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., role: _Optional[str] = ...) -> None: ...

class PublishIdentityKeyRequest(_message.Message):
    __slots__ = ("x25519_public_key",)
    X25519_PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    x25519_public_key: bytes
    def __init__(self, x25519_public_key: _Optional[bytes] = ...) -> None: ...

class PublishIdentityKeyResponse(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class GetIdentityKeyRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class GetIdentityKeyResponse(_message.Message):
    __slots__ = ("user_id", "username", "x25519_public_key")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    X25519_PUBLIC_KEY_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    username: str
    x25519_public_key: bytes
    def __init__(self, user_id: _Optional[str] = ..., username: _Optional[str] = ..., x25519_public_key: _Optional[bytes] = ...) -> None: ...
