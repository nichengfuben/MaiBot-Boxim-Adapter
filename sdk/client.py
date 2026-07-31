"""SDK 客户端与类型再导出。"""

from boxim import (
    AdminClient,
    BoxIM,
    BoxIMError,
    MessageType,
    WebSocketCommand,
)
from boxim.client import get_im_client

BoxIMMessageType = MessageType

__all__ = [
    "AdminClient",
    "BoxIM",
    "get_im_client",
    "BoxIMMessageType",
    "WebSocketCommand",
    "BoxIMError",
    "MessageType",
]
