"""BoxIM SDK 统一导入层。

所有对 boxim-sdk 的引用必须通过本模块，禁止在业务代码中直接 ``from boxim import ...``。
"""

from boxim import (
    AdminClient,
    BoxIM,
    BoxIMError,
    MessageType,
    WebSocketCommand,
)
from boxim.client import get_im_client
from boxim.util.data.emoji import (
    EMOJI_NAMES,
    EMOJI_NAME_TO_INDEX,
    EMOJI_PATTERN,
)

# 兼容旧别名
BoxIMMessageType = MessageType

__all__ = [
    "AdminClient",
    "BoxIM",
    "get_im_client",
    "EMOJI_NAMES",
    "EMOJI_NAME_TO_INDEX",
    "EMOJI_PATTERN",
    "BoxIMMessageType",
    "WebSocketCommand",
    "BoxIMError",
    "MessageType",
]
