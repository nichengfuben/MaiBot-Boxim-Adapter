from enum import Enum


class MetaEventType:
    lifecycle = "lifecycle"

    class Lifecycle:
        connect = "connect"

    heartbeat = "heartbeat"


class MessageType:
    private = "private"

    class Private:
        friend = "friend"

    group = "group"

    class Group:
        normal = "normal"


class NoticeType:
    friend_recall = "friend_recall"
    group_recall = "group_recall"
    notify = "notify"
    group_ban = "group_ban"
    group_upload = "group_upload"
    group_increase = "group_increase"
    group_decrease = "group_decrease"
    group_admin = "group_admin"

    class Notify:
        group_name = "group_name"

    class GroupBan:
        ban = "ban"
        lift_ban = "lift_ban"

    class GroupIncrease:
        approve = "approve"
        invite = "invite"

    class GroupDecrease:
        leave = "leave"
        kick = "kick"
        kick_me = "kick_me"

    class GroupAdmin:
        set = "set"
        unset = "unset"


class RealMessageType:
    text = "text"
    image = "image"
    record = "record"
    video = "video"
    at = "at"
    reply = "reply"
    forward = "forward"
    json = "json"
    file = "file"
    sticker = "sticker"


class MessageSentType:
    private = "private"

    class Private:
        friend = "friend"
        group = "group"

    group = "group"

    class Group:
        normal = "normal"


# CommandType 统一从 src 导入，避免重复定义
from src import CommandType  # noqa: E402, F401


ACCEPT_FORMAT = [
    "text", "image", "emoji", "reply", "voice", "command",
    "voiceurl", "music", "videourl", "file", "imageurl", "forward", "video",
]
