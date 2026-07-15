"""BoxIM SDK 统一导入层。

所有对 boxim-sdk 的引用必须通过本模块，禁止在业务代码中直接 ``from boxim import ...``。
"""

from boxim import BoxIM
from boxim.client import get_im_client
from boxim.util.emoji import (
    EMOJI_NAMES,
    EMOJI_NAME_TO_INDEX,
    EMOJI_PATTERN,
)
from boxim.util.types import MessageType as BoxIMMessageType, WebSocketCommand
from boxim.util.types import BoxIMError
from boxim.util.types import MessageType

__all__ = [
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
