from src.send_handler.im_api import (
    ImCoreMixin,
    ImMediaMixin,
    ImGroupMixin,
    ImSocialMixin,
    ImQueryMixin,
)


class BoxIMMessageSender(
    ImCoreMixin,
    ImMediaMixin,
    ImGroupMixin,
    ImSocialMixin,
    ImQueryMixin,
):
    """BoxIM SDK 消息发送器，封装所有 BoxIM 操作。"""


boxim_message_sender = BoxIMMessageSender()
