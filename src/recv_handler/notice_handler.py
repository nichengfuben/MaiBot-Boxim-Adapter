import time
import json
import asyncio
from typing import Tuple, Optional

from src.logger import logger
from src.config import global_config
from . import NoticeType, ACCEPT_FORMAT
from .message_sending import message_send_instance
from .message_handler import message_handler
from maim_message import FormatInfo, UserInfo, GroupInfo, Seg, BaseMessageInfo, MessageBase, SenderInfo


class NoticeHandler:
    """BoxIM 通知事件处理"""

    def __init__(self):
        pass

    async def handle_notice(self, msg_data: dict) -> None:
        """处理通知事件（入口方法）"""
        notice_type = msg_data.get("notice_type", "")
        
        if notice_type == "notify" or msg_data.get("post_type") == "notice":
            # 作为系统/通知消息处理
            await self.handle_system_message(msg_data)
        else:
            logger.debug(f"BoxIM 未处理的通知类型: {notice_type}")

    async def handle_system_message(self, msg_data: dict) -> None:
        """处理 BoxIM 系统消息"""
        message_time: float = time.time()
        msg_type: int = msg_data.get("type", 0)

        handled_message: Seg = None
        user_info: UserInfo = None
        group_id: Optional[int] = msg_data.get("groupId")
        sender_id: Optional[int] = msg_data.get("sendId")

        from sdk import BoxIMMessageType as BoxIMType, WebSocketCommand

        match msg_type:
            case BoxIMType.FRIEND_REQ_APPLY | BoxIMType.FRIEND_REQ_APPROVE | BoxIMType.FRIEND_REQ_REJECT | BoxIMType.FRIEND_REQ_RECALL:
                handled_message, user_info = await self._handle_friend_request(msg_data, msg_type)
            case BoxIMType.FRIEND_NEW:
                handled_message, user_info = await self._handle_friend_event(msg_data, "friend_add", "成为了好友")
            case BoxIMType.FRIEND_DEL:
                handled_message, user_info = await self._handle_friend_event(msg_data, "friend_del", "删除了好友")
            case BoxIMType.GROUP_NEW:
                handled_message, user_info = await self._handle_group_event(msg_data, "group_create", "创建了新群")
            case BoxIMType.GROUP_DEL:
                handled_message, user_info = await self._handle_group_event(msg_data, "group_dismiss", "解散了群")
            case WebSocketCommand.FORCE_OFFLINE:
                logger.error("BoxIM 账号被强制下线")
                return
            case BoxIMType.USER_LOGOUT:
                logger.warning("BoxIM 账号已退出")
                return
            case _:
                logger.debug(f"BoxIM 未处理的系统消息类型: {msg_type}")
                return

        if not handled_message or not user_info:
            logger.warning("系统消息处理失败")
            return None

        group_info: GroupInfo = None
        if group_id:
            group_info = GroupInfo(
                platform=global_config.maibot_server.platform_name,
                group_id=group_id,
                group_name="",
            )

        message_info = BaseMessageInfo(
            platform=global_config.maibot_server.platform_name,
            message_id="notice",
            time=message_time,
            user_info=user_info,
            group_info=group_info,
            sender_info=SenderInfo(
                group_info=group_info,
                user_info=user_info,
            ),
            template_info=None,
            format_info=FormatInfo(
                content_format=["text"],
                accept_format=ACCEPT_FORMAT,
            ),
            additional_config={},
        )

        message_base = MessageBase(
            message_info=message_info,
            message_segment=handled_message,
            raw_message=json.dumps(msg_data, ensure_ascii=False),
        )

        logger.info("发送到 MaiBot 处理通知信息")
        await message_send_instance.message_send(message_base)

    async def _handle_friend_request(self, msg_data: dict, msg_type: int) -> Tuple[Seg | None, UserInfo | None]:
        """处理好友请求相关通知"""
        sender_id = msg_data.get("sendId")
        send_nick = msg_data.get("sendNickName", "未知用户")

        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id or 0,
            user_nickname=send_nick,
            user_cardname=None,
        )

        from sdk import BoxIMMessageType as BoxIMType

        type_map = {
            BoxIMType.FRIEND_REQ_APPLY: "发送了好友请求",
            BoxIMType.FRIEND_REQ_APPROVE: "通过了好友请求",
            BoxIMType.FRIEND_REQ_REJECT: "拒绝了好友请求",
            BoxIMType.FRIEND_REQ_RECALL: "撤回了好友请求",
        }
        action = type_map.get(msg_type, "好友请求变动")

        return Seg(type="text", data=f"（通知：{send_nick} {action}）"), user_info

    async def _handle_friend_event(
        self, msg_data: dict, notice_subtype: str, action_text: str
    ) -> Tuple[Seg | None, UserInfo | None]:
        """处理好友变动通知"""
        sender_id = msg_data.get("sendId")
        send_nick = msg_data.get("sendNickName", "未知用户")

        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id or 0,
            user_nickname=send_nick,
            user_cardname=None,
        )

        return Seg(type="text", data=f"（通知：{send_nick} {action_text}）"), user_info

    async def _handle_group_event(
        self, msg_data: dict, notice_subtype: str, action_text: str
    ) -> Tuple[Seg | None, UserInfo | None]:
        """处理群事件通知"""
        sender_id = msg_data.get("sendId")
        send_nick = msg_data.get("sendNickName", "未知用户")
        group_id = msg_data.get("groupId")

        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id or 0,
            user_nickname=send_nick,
            user_cardname=None,
        )

        return Seg(type="text", data=f"（通知：{send_nick} {action_text}）"), user_info

    async def _handle_group_info_change(self, msg_data: dict) -> Tuple[Seg | None, UserInfo | None]:
        """处理群信息变更通知"""
        sender_id = msg_data.get("sendId")
        send_nick = msg_data.get("sendNickName", "未知用户")
        group_id = msg_data.get("groupId")
        content = msg_data.get("content", "")

        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id or 0,
            user_nickname=send_nick,
            user_cardname=None,
        )

        # 尝试解析群信息变更内容
        try:
            info = json.loads(content)
            new_name = info.get("group_name") or info.get("name")
            if new_name:
                return Seg(type="text", data=f"（通知：{send_nick} 修改群名称为: {new_name}）"), user_info
        except Exception:
            pass

        return Seg(type="text", data=f"（通知：群信息变更）"), user_info

    async def _handle_group_manager_change(self, msg_data: dict) -> Tuple[Seg | None, UserInfo | None]:
        """处理群管理员变动通知"""
        sender_id = msg_data.get("sendId")
        send_nick = msg_data.get("sendNickName", "未知用户")
        content = msg_data.get("content", "")

        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id or 0,
            user_nickname=send_nick,
            user_cardname=None,
        )

        # 尝试解析是设置还是取消管理员
        try:
            info = json.loads(content)
            is_set = info.get("is_manager") or info.get("set")
            action = "被设置为管理员" if is_set else "被取消管理员"
            return Seg(type="text", data=f"（通知：{send_nick} {action}）"), user_info
        except Exception:
            pass

        return Seg(type="text", data=f"（通知：管理员变动）"), user_info


notice_handler = NoticeHandler()
