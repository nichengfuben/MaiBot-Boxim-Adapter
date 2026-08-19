import asyncio
import time
import json
import base64
from typing import List, Tuple, Optional, Dict, Any

from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
    TemplateInfo,
    FormatInfo,
    SenderInfo,
)

from src.runtime.logger import logger
from src.config import global_config
from src.runtime.utils import get_image_base64
from .face_map import boxim_face
from .content import parse_boxim_content
from .message_sending import message_send_instance
from . import RealMessageType, MessageType, ACCEPT_FORMAT

import re
import aiohttp


class MessageHandler:
    def __init__(self):
        self.bot_user_id: Optional[int] = None
        self.bot_nickname: str = ""
        self._user_cache: Dict[int, str] = {}  # user_id -> user_name cache
        self._group_cache: Dict[int, str] = {}  # group_id -> group_name cache
        # 消息去重集合（防止离线拉取与实时 WebSocket 重叠导致重复）
        self._processed_msg_ids: set[int] = set()
        self._max_dedup_size = 5000
        # 离线状态持久化：跟踪最大消息 ID（实时 + 离线消息均更新）
        self._state_file: str = ""
        self._max_private_id: int = 0
        self._max_group_id: int = 0
        self._dirty_count: int = 0
        self._save_interval: int = 50  # 每处理50条消息保存一次

    def init_offline_state(self, state_file: str, last_private_id: int, last_group_id: int) -> None:
        """初始化离线状态追踪，由 main.py 在启动时调用。"""
        self._state_file = state_file
        self._max_private_id = last_private_id
        self._max_group_id = last_group_id

    def _update_max_id(self, msg_id: int, is_group: bool) -> None:
        """更新最大消息 ID 并定期持久化。"""
        if is_group:
            if msg_id > self._max_group_id:
                self._max_group_id = msg_id
                self._dirty_count += 1
        else:
            if msg_id > self._max_private_id:
                self._max_private_id = msg_id
                self._dirty_count += 1
        if self._dirty_count >= self._save_interval:
            self.save_offline_state()

    def save_offline_state(self) -> None:
        """持久化当前最大消息 ID。"""
        if not self._state_file:
            return
        self._dirty_count = 0
        try:
            import json, os
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            with open(self._state_file, "w") as f:
                json.dump({
                    "last_private_id": self._max_private_id,
                    "last_group_id": self._max_group_id,
                }, f)
        except Exception as e:
            logger.debug(f"保存离线状态失败: {e}")

    def is_duplicate(self, msg_id) -> bool:
        """检查消息是否已处理过。"""
        if msg_id is None:
            return False
        msg_id = int(msg_id)
        if msg_id in self._processed_msg_ids:
            return True
        self._processed_msg_ids.add(msg_id)
        if len(self._processed_msg_ids) > self._max_dedup_size:
            excess = len(self._processed_msg_ids) - self._max_dedup_size
            to_remove = sorted(self._processed_msg_ids)[:excess]
            for mid in to_remove:
                self._processed_msg_ids.discard(mid)
        return False

    def set_bot_info(self, user_id: int, nickname: str) -> None:
        self.bot_user_id = user_id
        self.bot_nickname = nickname

    def set_boxim_client(self, client):
        """设置 BoxIM SDK 引用用于查询用户信息"""
        self._boxim_client = client

    async def _get_real_username(self, user_id: int, msg_data: dict) -> str:
        """通过消息自带的昵称或 BoxIM SDK 查询用户真实用户名，带缓存"""
        # 如果是 bot 自己发的消息，直接返回 bot_nickname
        if self.bot_user_id is not None and user_id == self.bot_user_id:
            return self.bot_nickname or f"用户{user_id}"
        if user_id in self._user_cache:
            logger.debug(f"用户 {user_id} 缓存用户名: {self._user_cache[user_id]}")
            return self._user_cache[user_id]
        # 优先用消息自带的 sendNickName
        send_nick = msg_data.get("sendNickName", "")
        if send_nick:
            self._user_cache[user_id] = send_nick
            logger.debug(f"用户 {user_id} 使用消息自带昵称: {send_nick}")
            return send_nick
        # 消息没有昵称时尝试用 SDK 查询
        try:
            if hasattr(self, '_boxim_client') and self._boxim_client:
                user = await self._boxim_client.aget_user(user_id)
                logger.debug(f"BoxIM SDK 返回用户 {user_id} 信息: user_name={user.user_name!r}, nick_name={user.nick_name!r}")
                username = user.nick_name or user.user_name or f"用户{user_id}"
                logger.debug(f"用户 {user_id} 使用用户名: {username}")
                self._user_cache[user_id] = username
                return username
        except Exception as e:
            logger.debug(f"查询用户 {user_id} 信息失败: {e}")
        self._user_cache[user_id] = f"用户{user_id}"
        return self._user_cache[user_id]

    async def _get_real_group_name(self, group_id: int) -> str:
        """通过 BoxIM SDK 查询真实群名，带缓存"""
        if group_id in self._group_cache:
            logger.debug(f"群 {group_id} 缓存群名: {self._group_cache[group_id]}")
            return self._group_cache[group_id]
        try:
            if hasattr(self, '_boxim_client') and self._boxim_client:
                group = await self._boxim_client.aget_group_info(group_id)
                logger.debug(f"BoxIM SDK 返回群 {group_id} 信息: name={group.name!r}")
                group_name = group.name or f"群{group_id}"
                logger.debug(f"群 {group_id} 使用群名: {group_name}")
                self._group_cache[group_id] = group_name
                return group_name
        except Exception as e:
            logger.debug(f"查询群 {group_id} 信息失败: {e}")
        self._group_cache[group_id] = f"群{group_id}"
        return self._group_cache[group_id]

    async def check_allow_to_chat(
        self,
        user_id: int,
        group_id: Optional[int] = None,
    ) -> bool:
        """检查是否允许聊天"""
        logger.debug(f"群聊id: {group_id}, 用户id: {user_id}")
        if group_id:
            if global_config.chat.group_list_type == "whitelist" and group_id not in global_config.chat.group_list:
                logger.warning("群聊不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.chat.group_list_type == "blacklist" and group_id in global_config.chat.group_list:
                logger.warning("群聊在聊天黑名单中，消息被丢弃")
                return False
        else:
            if global_config.chat.private_list_type == "whitelist" and user_id not in global_config.chat.private_list:
                logger.warning("私聊不在聊天白名单中，消息被丢弃")
                return False
            elif global_config.chat.private_list_type == "blacklist" and user_id in global_config.chat.private_list:
                logger.warning("私聊在聊天黑名单中，消息被丢弃")
                return False
        if user_id in global_config.chat.ban_user_id:
            logger.warning("用户在全局黑名单中，消息被丢弃")
            return False
        return True

    async def handle_boxim_message(self, msg_data: dict, is_group: bool) -> None:
        """处理来自 BoxIM SDK 的原始消息（camelCase 格式）"""
        message_id = msg_data.get("id")
        msg_type = msg_data.get("type", 0)
        if not self._precheck_message(message_id, msg_type):
            return
        self._update_max_id(message_id, is_group)
        message_time = msg_data.get("sendTime", 0) / 1000 if msg_data.get("sendTime") else time.time()
        sender_id = msg_data.get("sendId")
        group_id = msg_data.get("groupId") if is_group else None
        if sender_id is None or self._is_self_message(sender_id, message_id):
            return
        user_info, group_info = await self._build_chat_context(sender_id, group_id, is_group, msg_data)
        if user_info is None:
            return
        content = msg_data.get("content", "")
        seg_message, additional_config = await parse_boxim_content(
            self, msg_data.get("type", 0), content, msg_data
        )
        if global_config.voice.use_tts:
            additional_config["allow_tts"] = True
        if not seg_message:
            logger.warning("处理后消息内容为空")
            return None
        await self._forward_to_maibot(
            message_id, message_time, user_info, group_info, seg_message, additional_config, msg_data, content
        )
        asyncio.create_task(self._auto_mark_read(sender_id, group_id))

    def _precheck_message(self, message_id, msg_type) -> bool:
        no_id = {11, 12, 53, 54, 82} | set(range(100, 110)) | set(range(200, 212)) | set(range(220, 227))
        if message_id is None:
            if msg_type not in no_id:
                logger.warning(f"BoxIM 消息缺少 id，type={msg_type}，跳过")
            return False
        if self.is_duplicate(message_id):
            logger.debug(f"跳过重复消息: id={message_id}")
            return False
        return True

    def _is_self_message(self, sender_id: int, message_id: int) -> bool:
        if self.bot_user_id is not None and sender_id == self.bot_user_id:
            logger.debug(f"跳过 bot 自身发送的消息: id={message_id}, sendId={sender_id}")
            return True
        return False

    async def _build_chat_context(self, sender_id, group_id, is_group, msg_data):
        if is_group:
            if not await self.check_allow_to_chat(sender_id, group_id):
                return None, None
            real_username = await self._get_real_username(sender_id, msg_data)
            real_groupname = await self._get_real_group_name(group_id)
            user_info = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=sender_id,
                user_nickname=real_username,
                user_cardname=msg_data.get("sendNickName"),
            )
            group_info = GroupInfo(
                platform=global_config.maibot_server.platform_name,
                group_id=group_id,
                group_name=real_groupname,
            )
            return user_info, group_info
        if not await self.check_allow_to_chat(sender_id):
            return None, None
        real_username = await self._get_real_username(sender_id, msg_data)
        user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id,
            user_nickname=real_username,
            user_cardname=None,
        )
        return user_info, None

    async def _forward_to_maibot(
        self, message_id, message_time, user_info, group_info, seg_message, additional_config, msg_data, content
    ):
        submit_seg = Seg(type="seglist", data=seg_message)
        sender_info = SenderInfo(group_info=group_info, user_info=user_info)
        # 根据实际消息内容动态设置 content_format
        content_types = set()
        for seg in seg_message:
            if seg.type == "text":
                content_types.add("text")
            elif seg.type == "image":
                content_types.add("image")
            elif seg.type == "emoji":
                content_types.add("emoji")
            elif seg.type == "voice":
                content_types.add("voice")
            elif seg.type == "file":
                content_types.add("file")
            elif seg.type == "reply":
                content_types.add("reply")
            elif seg.type == "at":
                content_types.add("at")
            elif seg.type == "notify":
                content_types.add("notify")
        if not content_types:
            content_types.add("text")
        message_info = BaseMessageInfo(
            platform=global_config.maibot_server.platform_name,
            message_id=message_id,
            time=message_time,
            user_info=user_info,
            group_info=group_info,
            sender_info=sender_info,
            template_info=None,
            format_info=FormatInfo(
                content_format=list(content_types),
                accept_format=ACCEPT_FORMAT,
            ),
            additional_config=additional_config,
        )
        message_base = MessageBase(
            message_info=message_info,
            message_segment=submit_seg,
            raw_message=json.dumps(msg_data, ensure_ascii=False),
        )
        logger.info(
            f"发送到 MaiBot 处理信息, 解析结果: segs={[s.type for s in seg_message]}, raw_content={content[:200]}"
        )
        await message_send_instance.message_send(message_base)


    async def _auto_mark_read(self, sender_id: int, group_id: Optional[int]) -> None:
        """延迟 0.5 秒后标记消息已读"""
        try:
            await asyncio.sleep(0.5)
            if hasattr(self, '_boxim_client') and self._boxim_client:
                if group_id:
                    await self._boxim_client.amark_group_read(group_id)
                    logger.debug(f"已标记群 {group_id} 消息为已读")
                else:
                    await self._boxim_client.amark_private_read(sender_id)
                    logger.debug(f"已标记私聊 {sender_id} 消息为已读")
        except Exception as e:
            logger.debug(f"标记已读失败: {e}")



    async def _get_sticker_image_url(self, sticker_id: int) -> Optional[str]:
        """获取贴纸图片 URL（通过 BoxIM SDK 查询）"""
        try:
            from sdk import get_im_client
            im = get_im_client()
            # 尝试从自定义贴纸中查找
            custom_stickers = await im.aget_custom_stickers()
            for s in custom_stickers:
                if s.id == sticker_id:
                    return s.image_url or s.thumb_url
            # 尝试从相册查找
            albums = await im.aget_sticker_albums()
            for album in albums[:3]:  # 限制查找前3个相册避免过多请求
                stickers = await im.aget_stickers(album.id)
                for s in stickers:
                    if s.id == sticker_id:
                        return s.image_url or s.thumb_url
        except Exception as e:
            logger.debug(f"获取贴纸 URL 失败: {e}")
        return None

    async def _download_url(self, url: str) -> Optional[bytes]:
        """下载 URL 内容"""
        try:
            timeout = global_config.media.download_timeout
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    logger.error(f"下载失败: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"下载失败: {e}")
        return None


message_handler = MessageHandler()
