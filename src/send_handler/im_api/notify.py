"""Business error notification helpers."""
from __future__ import annotations

import json
import time
from typing import Optional

from maim_message import (
    FormatInfo,
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
    SenderInfo,
)

from src.config import global_config
from src.recv_handler.message_sending import message_send_instance
from src.runtime.logger import logger

_ERROR_DESC = {
    "friend_removed": "（系统提示：你尝试向用户发送消息时，平台返回了好友关系异常的错误。该消息可能未送达，建议先确认好友关系是否正常。）",
    "group_muted": "（系统提示：你尝试在群聊中发送消息失败，因为你已被该群禁言。你可能需要在回复中注意这一点。）",
    "group_kicked": "（系统提示：你已被该群踢出，无法继续发送消息。）",
    "group_not_found": "（系统提示：目标群聊不存在，无法发送消息。）",
    "user_not_found": "（系统提示：目标用户不存在，无法发送消息。）",
}


def build_error_description(
    error_type: str, user_id: Optional[int], group_id: Optional[int], error_code: Optional[int]
) -> str:
    description = _ERROR_DESC.get(error_type, "（系统提示：业务操作失败。）")
    if user_id:
        description = description.replace("用户", f"用户（ID: {user_id}）")
    if group_id:
        description = description.replace("群聊", f"群聊（ID: {group_id}）")
    if error_code is not None:
        description += f"（错误码: {error_code}）"
    return description


def _build_error_message(
    user_id, group_id, error_type, error_message, error_code, description
):
    platform_name = global_config.maibot_server.platform_name
    user_info = UserInfo(
        platform=platform_name, user_id=user_id or 0, user_nickname="系统", user_cardname=None
    )
    group_info = (
        GroupInfo(platform=platform_name, group_id=group_id, group_name="")
        if group_id
        else None
    )
    message_info = BaseMessageInfo(
        platform=platform_name,
        message_id="notice",
        time=time.time(),
        user_info=user_info,
        group_info=group_info,
        sender_info=SenderInfo(group_info=group_info, user_info=user_info),
        template_info=None,
        format_info=FormatInfo(
            content_format=["text"],
            accept_format=["text", "image", "emoji", "reply", "voice", "command"],
        ),
        additional_config={
            "business_error": {
                "error_type": error_type,
                "error_message": error_message,
                "error_code": error_code,
                "user_id": user_id,
                "group_id": group_id,
            }
        },
    )
    raw = {
        "error_type": error_type,
        "error_message": error_message,
        "error_code": error_code,
        "description": description,
        "user_id": user_id,
        "group_id": group_id,
    }
    return MessageBase(
        message_info=message_info,
        message_segment=Seg(type="text", data=description),
        raw_message=json.dumps(raw, ensure_ascii=False),
    )


async def send_business_error(
    user_id: Optional[int],
    group_id: Optional[int],
    error_type: str,
    error_message: str,
    error_code: Optional[int] = None,
) -> None:
    description = build_error_description(error_type, user_id, group_id, error_code)
    message_base = _build_error_message(
        user_id, group_id, error_type, error_message, error_code, description
    )
    try:
        await message_send_instance.message_send(message_base)
        logger.debug(f"已发送业务错误通知: {error_type}")
    except Exception as e:
        logger.error(f"发送业务错误通知失败: {e}")
