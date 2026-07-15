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

from src.logger import logger
from src.config import global_config
from src.utils import get_image_base64
from .boxim_emoji_list import boxim_face, STICKER_NAME_TO_ID, INLINE_STICKER_PATTERN
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
        message_id: int = msg_data.get("id")
        msg_type: int = msg_data.get("type", 0)
        if message_id is None:
            # 系统/通知消息没有 id 是正常的
            NO_ID_TYPES = {11, 12, 53, 54, 82, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 220, 221, 222, 223, 224, 225, 226}
            if msg_type in NO_ID_TYPES:
                return
            logger.warning(f"BoxIM 消息缺少 id，type={msg_type}，跳过")
            return

        # 消息去重（离线拉取与实时 WebSocket 可能重叠）
        if self.is_duplicate(message_id):
            logger.debug(f"跳过重复消息: id={message_id}")
            return

        # 更新最大消息 ID（实时 + 离线消息均记录）
        self._update_max_id(message_id, is_group)

        message_time: float = msg_data.get("sendTime", 0) / 1000 if msg_data.get("sendTime") else time.time()
        sender_id: int = msg_data.get("sendId")
        group_id: Optional[int] = msg_data.get("groupId") if is_group else None

        if sender_id is None:
            logger.warning("BoxIM 消息缺少 sendId，跳过")
            return

        # 兜底过滤：bot 自己发送的消息不应被当作新消息处理
        # SDK 层已有过滤（WebSocketTransport._is_self_message），
        # 此处作为双保险，防止 SDK 未设置 bot_user_id 时漏过
        if self.bot_user_id is not None and sender_id == self.bot_user_id:
            logger.debug(f"跳过 bot 自身发送的消息: id={message_id}, sendId={sender_id}")
            return

        if is_group:
            if not await self.check_allow_to_chat(sender_id, group_id):
                return
            real_username = await self._get_real_username(sender_id, msg_data)
            real_groupname = await self._get_real_group_name(group_id)
            # BoxIM 不区分群名片，用消息自带的 sendNickName 作为群名片
            user_cardname = msg_data.get("sendNickName")
            logger.debug(f"群消息 UserInfo: user_id={sender_id}, user_nickname={real_username!r}, user_cardname={user_cardname!r}, group_name={real_groupname!r}")
            user_info = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=sender_id,
                user_nickname=real_username,
                user_cardname=user_cardname,
            )
            group_info = GroupInfo(
                platform=global_config.maibot_server.platform_name,
                group_id=group_id,
                group_name=real_groupname,
            )
        else:
            if not await self.check_allow_to_chat(sender_id):
                return
            real_username = await self._get_real_username(sender_id, msg_data)
            logger.debug(f"私聊 UserInfo: user_id={sender_id}, user_nickname={real_username!r}")
            user_info = UserInfo(
                platform=global_config.maibot_server.platform_name,
                user_id=sender_id,
                user_nickname=real_username,
                user_cardname=None,
            )
            group_info = None

        msg_type: int = msg_data.get("type", 0)
        content: str = msg_data.get("content", "")

        seg_message, additional_config = await self._parse_boxim_content(msg_type, content, msg_data)

        if global_config.voice.use_tts:
            additional_config["allow_tts"] = True

        if not seg_message:
            logger.warning("处理后消息内容为空")
            return None

        submit_seg = Seg(type="seglist", data=seg_message)

        sender_info = SenderInfo(
            group_info=group_info,
            user_info=user_info,
        )

        message_info = BaseMessageInfo(
            platform=global_config.maibot_server.platform_name,
            message_id=message_id,
            time=message_time,
            user_info=user_info,
            group_info=group_info,
            sender_info=sender_info,
            template_info=None,
            format_info=FormatInfo(
                content_format=["text", "image", "emoji", "voice"],
                accept_format=ACCEPT_FORMAT,
            ),
            additional_config=additional_config,
        )

        message_base = MessageBase(
            message_info=message_info,
            message_segment=submit_seg,
            raw_message=json.dumps(msg_data, ensure_ascii=False),
        )

        logger.info(f"发送到 MaiBot 处理信息, 解析结果: segs={[s.type for s in seg_message]}, raw_content={content[:200]}")
        logger.debug(f"MessageBase sender_info: {sender_info.to_dict()}")
        await message_send_instance.message_send(message_base)

        # 0.5 秒后自动标记已读
        asyncio.create_task(self._auto_mark_read(sender_id, group_id))

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

    async def _parse_boxim_content(
        self, msg_type: int, content: str, msg_data: dict
    ) -> Tuple[List[Seg] | None, Dict[str, Any]]:
        """解析 BoxIM 消息内容，返回 Seg 列表和 additional_config"""
        from sdk import BoxIMMessageType as BoxIMType

        additional_config: dict = {}
        seg_message: List[Seg] = []

        # 处理引用消息
        quote_msg_id = msg_data.get("quoteMessageId")
        if quote_msg_id:
            additional_config["reply_message_id"] = str(quote_msg_id)
            seg_message.append(Seg(type="reply", data=str(quote_msg_id)))

        # 处理 at
        at_user_ids = msg_data.get("atUserIds") or []
        for at_uid in at_user_ids:
            seg_message.append(Seg(type="at", data={"user_id": at_uid}))

        if msg_type == BoxIMType.TEXT:
            # 文本消息：解析内联表情 #名称;
            text_segs = await self._parse_text_with_inline_stickers(content)
            seg_message.extend(text_segs)

        elif msg_type == BoxIMType.IMAGE:
            try:
                img_info = json.loads(content)
                url = img_info.get("originUrl") or img_info.get("url") or img_info.get("origin_url") or ""
                if url:
                    image_base64 = await get_image_base64(url)
                    seg_message.append(Seg(type="image", data=image_base64))
                else:
                    logger.warning("BoxIM 图片消息缺少 URL")
            except Exception as e:
                logger.error(f"BoxIM 图片解析失败: {e}")

        elif msg_type == BoxIMType.STICKER:
            try:
                sticker_info = json.loads(content)
                # 支持多种 content 格式:
                # 1. {"stickerId": 42}  (Napcat 发出的格式)
                # 2. {"id": 42, "name": "憨笑", "imageUrl": "..."}  (BoxIM 服务器推送的完整格式)
                # 3. {"sticker_id": 42}  (snake_case 备选)
                sticker_id = (
                    sticker_info.get("stickerId")
                    or sticker_info.get("sticker_id")
                    or sticker_info.get("id")
                )
                sticker_name = sticker_info.get("name", "")

                if sticker_id is not None:
                    sticker_id = int(sticker_id)
                    # 优先使用服务器返回的名称，其次查表
                    if not sticker_name:
                        sticker_name = boxim_face.get(str(sticker_id), f"[表情：贴纸{sticker_id}]")
                    if global_config.sticker.download_as_emoji:
                        # 下载贴纸图片作为 emoji 发送
                        # 如果 content 中已有 imageUrl，直接使用
                        image_url = sticker_info.get("imageUrl") or sticker_info.get("image_url")
                        if not image_url:
                            image_url = await self._get_sticker_image_url(sticker_id)
                        if image_url:
                            try:
                                emoji_b64 = await get_image_base64(image_url)
                                seg_message.append(Seg(type="emoji", data=emoji_b64))
                            except Exception as e:
                                logger.error(f"下载贴纸图片失败: {e}")
                                seg_message.append(Seg(type="text", data=sticker_name))
                        else:
                            # 无法获取图片时降级为文本
                            seg_message.append(Seg(type="text", data=sticker_name))
                    else:
                        seg_message.append(Seg(type="text", data=sticker_name))
                else:
                    # 没有 stickerId，尝试用 imageUrl 直接下载作为 emoji
                    image_url = sticker_info.get("imageUrl") or sticker_info.get("image_url") or sticker_info.get("thumbUrl")
                    if sticker_name:
                        seg_message.append(Seg(type="text", data=sticker_name))
                    elif image_url and global_config.sticker.download_as_emoji:
                        try:
                            emoji_b64 = await get_image_base64(image_url)
                            seg_message.append(Seg(type="emoji", data=emoji_b64))
                        except Exception as e:
                            logger.warning(f"BoxIM 贴纸无 stickerId，下载 imageUrl 失败: {e}")
                            seg_message.append(Seg(type="text", data="[表情]"))
                    else:
                        logger.warning(f"BoxIM 贴纸消息缺少 stickerId，原始内容: {content[:200]}")
                        seg_message.append(Seg(type="text", data="[表情]"))
            except Exception as e:
                logger.error(f"BoxIM 贴纸解析失败: {e}")
                seg_message.append(Seg(type="text", data="[表情]"))

        elif msg_type == BoxIMType.VOICE:
            try:
                voice_info = json.loads(content)
                url = voice_info.get("url") or voice_info.get("voice_url") or ""
                if url:
                    voice_bytes = await self._download_url(url)
                    if voice_bytes:
                        voice_base64 = base64.b64encode(voice_bytes).decode("utf-8")
                        seg_message.append(Seg(type="voice", data=voice_base64))
                else:
                    logger.warning("BoxIM 语音消息缺少 URL")
            except Exception as e:
                logger.error(f"BoxIM 语音解析失败: {e}")

        elif msg_type == BoxIMType.VIDEO:
            try:
                video_info = json.loads(content)
                url = video_info.get("videoUrl") or video_info.get("video_url") or video_info.get("url") or ""
                cover_url = video_info.get("coverUrl") or video_info.get("cover_url") or ""
                file_name = video_info.get("fileName") or video_info.get("file_name") or "视频"
                file_size = video_info.get("fileSize") or video_info.get("file_size") or "未知大小"

                # 优先下载封面图供 VLM 解析
                if cover_url:
                    try:
                        cover_base64 = await get_image_base64(cover_url)
                        seg_message.append(Seg(type="image", data=cover_base64))
                    except Exception as e:
                        logger.debug(f"视频封面下载失败: {e}")

                # 附加视频文本描述
                seg_message.append(Seg(type="text", data=f"[视频: {file_name}, 大小: {file_size}字节]"))
            except Exception as e:
                logger.error(f"BoxIM 视频解析失败: {e}")

        elif msg_type == BoxIMType.FILE:
            try:
                file_info = json.loads(content)
                file_name = file_info.get("name") or file_info.get("fileName") or file_info.get("file_name") or "未知文件"
                file_size = file_info.get("size") or file_info.get("fileSize") or file_info.get("file_size") or "未知大小"

                # 检测是否为图片文件，是则下载为 base64 供 VLM 解析
                _IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
                is_image = any(file_name.lower().endswith(ext) for ext in _IMAGE_EXTS)
                if is_image:
                    url = (
                        file_info.get("url")
                        or file_info.get("originUrl")
                        or file_info.get("origin_url")
                        or ""
                    )
                    if url:
                        image_base64 = await get_image_base64(url)
                        seg_message.append(Seg(type="image", data=image_base64))
                    else:
                        # 图片文件但没有 URL，降级为文本
                        seg_message.append(Seg(type="text", data=f"[图片文件: {file_name}, 大小: {file_size}字节]"))
                else:
                    file_text = f"[文件: {file_name}, 大小: {file_size}字节]"
                    seg_message.append(Seg(type="text", data=file_text))
            except Exception as e:
                logger.error(f"BoxIM 文件解析失败: {e}")

        elif msg_type == BoxIMType.TIP_TEXT or msg_type == BoxIMType.SYSTEM_MESSAGE:
            seg_message.append(Seg(type="text", data=content))

        elif msg_type == BoxIMType.MERGE_FORWARD:
            # 合并转发消息
            try:
                forward_data = json.loads(content)
                # BoxIM 合并转发：具体结构取决于服务端实现
                if isinstance(forward_data, dict):
                    forward_text = forward_data.get("summary") or forward_data.get("title") or "[合并转发消息]"
                    seg_message.append(Seg(type="text", data=f"[合并转发] {forward_text}"))
                elif isinstance(forward_data, list):
                    for item in forward_data:
                        if isinstance(item, dict):
                            sender = item.get("sender_name") or item.get("nickname") or "未知用户"
                            text = item.get("content") or item.get("text") or ""
                            seg_message.append(Seg(type="text", data=f"【{sender}】: {text}"))
            except Exception as e:
                logger.error(f"BoxIM 合并转发解析失败: {e}")
                seg_message.append(Seg(type="text", data="[合并转发消息]"))

        elif msg_type == BoxIMType.RECALL:
            is_group_recall = bool(msg_data.get("groupId"))
            sub_type = "group_recall" if is_group_recall else "friend_recall"

            # 获取被撤回的消息 ID
            recalled_message_id = msg_data.get("recallMessageId") or msg_data.get("id")

            # 构建撤回者信息
            recalled_user_info = None
            if is_group_recall:
                sender_id = msg_data.get("sendId")
                if sender_id:
                    sender_name = await self._get_real_username(sender_id, msg_data)
                    recalled_user_info = UserInfo(
                        platform=global_config.maibot_server.platform_name,
                        user_id=sender_id,
                        user_nickname=sender_name,
                        user_cardname=None,
                    ).to_dict()

            seg_message.append(Seg(
                type="notify",
                data={
                    "sub_type": sub_type,
                    "message_id": recalled_message_id,
                    "recalled_user_info": recalled_user_info,
                },
            ))

        elif msg_type == BoxIMType.USER_CARD:
            try:
                card_info = json.loads(content)
                nick = card_info.get("nick_name") or card_info.get("nickname") or "未知用户"
                seg_message.append(Seg(type="text", data=f"[推荐联系人] {nick}"))
            except Exception:
                seg_message.append(Seg(type="text", data="[推荐联系人]"))

        elif msg_type == BoxIMType.GROUP_CARD:
            try:
                card_info = json.loads(content)
                name = card_info.get("group_name") or card_info.get("name") or "未知群聊"
                seg_message.append(Seg(type="text", data=f"[推荐群聊] {name}"))
            except Exception:
                seg_message.append(Seg(type="text", data="[推荐群聊]"))

        elif msg_type in (BoxIMType.RTC_CALL_VOICE, BoxIMType.RTC_CALL_VIDEO):
            call_type = "语音通话" if msg_type == BoxIMType.RTC_CALL_VOICE else "视频通话"
            seg_message.append(Seg(type="text", data=f"[{call_type}]"))

        else:
            logger.debug(f"BoxIM 未处理的消息类型: {msg_type}")
            # 默认作为文本
            if content:
                seg_message.append(Seg(type="text", data=f"[类型{msg_type}] {content[:100]}"))

        return seg_message if seg_message else None, additional_config

    async def _parse_text_with_inline_stickers(self, text: str) -> List[Seg]:
        """解析文本中的内联表情 #名称; 并替换为 Seg"""
        segs: List[Seg] = []
        last_end = 0
        for match in re.finditer(INLINE_STICKER_PATTERN, text):
            start, end = match.start(), match.end()
            name = match.group(1)
            sticker_id = STICKER_NAME_TO_ID.get(name)

            # 添加前面的纯文本
            if start > last_end:
                plain = text[last_end:start]
                if plain:
                    segs.append(Seg(type="text", data=plain))

            if sticker_id is not None:
                sticker_name = boxim_face.get(str(sticker_id), f"[表情：{name}]")
                if global_config.sticker.download_as_emoji:
                    # 下载贴纸图片为 base64，与直接 Sticker 类型保持一致
                    image_url = await self._get_sticker_image_url(sticker_id)
                    if image_url:
                        try:
                            emoji_b64 = await get_image_base64(image_url)
                            segs.append(Seg(type="emoji", data=emoji_b64))
                        except Exception as e:
                            logger.error(f"下载内联贴纸图片失败: {e}")
                            segs.append(Seg(type="text", data=sticker_name))
                    else:
                        # 无法获取图片时降级为文本
                        segs.append(Seg(type="text", data=sticker_name))
                else:
                    segs.append(Seg(type="text", data=sticker_name))
            else:
                segs.append(Seg(type="text", data=match.group(0)))

            last_end = end

        if last_end < len(text):
            remaining = text[last_end:]
            if remaining:
                segs.append(Seg(type="text", data=remaining))

        if not segs:
            segs.append(Seg(type="text", data=text))

        return segs

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
