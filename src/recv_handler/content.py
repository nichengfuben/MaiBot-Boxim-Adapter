"""Parse BoxIM message content into MaiBot Seg list."""

from __future__ import annotations

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from maim_message import Seg, UserInfo

from src.config import global_config
from src.runtime.logger import logger
from src.runtime.utils import get_image_base64
from src.recv_handler.face_map import boxim_face, STICKER_NAME_TO_ID, INLINE_STICKER_PATTERN


async def parse_boxim_content(
    handler: Any,
    msg_type: int,
    content: str,
    msg_data: dict,
) -> Tuple[List[Seg] | None, Dict[str, Any]]:
    """解析 BoxIM 消息内容，返回 Seg 列表和 additional_config。"""
    from sdk import BoxIMMessageType as BoxIMType

    additional_config: dict = {}
    segs: List[Seg] = []

    quote_msg_id = msg_data.get("quoteMessageId")
    if quote_msg_id:
        additional_config["reply_message_id"] = str(quote_msg_id)
        segs.append(Seg(type="reply", data=str(quote_msg_id)))

    for at_uid in msg_data.get("atUserIds") or []:
        segs.append(Seg(type="at", data={"user_id": at_uid}))

    parser = _PARSERS.get(int(msg_type))
    if parser is not None:
        await parser(handler, content, msg_data, segs)
    elif msg_type in (BoxIMType.TIP_TEXT, BoxIMType.SYSTEM_MESSAGE):
        segs.append(Seg(type="text", data=content))
    elif msg_type in (BoxIMType.RTC_CALL_VOICE, BoxIMType.RTC_CALL_VIDEO):
        label = "语音通话" if msg_type == BoxIMType.RTC_CALL_VOICE else "视频通话"
        segs.append(Seg(type="text", data=f"[{label}]"))
    else:
        logger.debug(f"BoxIM 未处理的消息类型: {msg_type}")
        if content:
            segs.append(Seg(type="text", data=f"[类型{msg_type}] {content[:100]}"))

    return (segs if segs else None), additional_config


async def parse_text_stickers(handler: Any, text: str) -> List[Seg]:
    """解析文本中的内联表情 #名称;。"""
    segs: List[Seg] = []
    last_end = 0
    for match in re.finditer(INLINE_STICKER_PATTERN, text):
        start, end = match.start(), match.end()
        if start > last_end and text[last_end:start]:
            segs.append(Seg(type="text", data=text[last_end:start]))
        await _append_inline_sticker(handler, match, segs)
        last_end = end
    if last_end < len(text) and text[last_end:]:
        segs.append(Seg(type="text", data=text[last_end:]))
    if not segs:
        segs.append(Seg(type="text", data=text))
    return segs


async def _append_inline_sticker(handler: Any, match: re.Match, segs: List[Seg]) -> None:
    name = match.group(1)
    sticker_id = STICKER_NAME_TO_ID.get(name)
    if sticker_id is None:
        segs.append(Seg(type="text", data=match.group(0)))
        return
    sticker_name = boxim_face.get(str(sticker_id), f"[表情：{name}]")
    if not global_config.sticker.download_as_emoji:
        segs.append(Seg(type="text", data=sticker_name))
        return
    image_url = await handler._get_sticker_image_url(sticker_id)
    if not image_url:
        segs.append(Seg(type="text", data=sticker_name))
        return
    try:
        segs.append(Seg(type="emoji", data=await get_image_base64(image_url)))
    except Exception as e:
        logger.error(f"下载内联贴纸图片失败: {e}")
        segs.append(Seg(type="text", data=sticker_name))


async def _parse_text(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    segs.extend(await parse_text_stickers(handler, content))


async def _parse_image(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        img_info = json.loads(content)
        url = img_info.get("originUrl") or img_info.get("url") or img_info.get("origin_url") or ""
        if not url:
            logger.warning("BoxIM 图片消息缺少 URL")
            return
        segs.append(Seg(type="image", data=await get_image_base64(url)))
    except Exception as e:
        logger.error(f"BoxIM 图片解析失败: {e}")


async def _parse_sticker(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        info = json.loads(content)
        sticker_id = info.get("stickerId") or info.get("sticker_id") or info.get("id")
        sticker_name = info.get("name", "")
        if sticker_id is None:
            await _sticker_without_id(info, sticker_name, segs)
            return
        sticker_id = int(sticker_id)
        if not sticker_name:
            sticker_name = boxim_face.get(str(sticker_id), f"[表情：贴纸{sticker_id}]")
        await _sticker_with_id(handler, info, sticker_id, sticker_name, segs)
    except Exception as e:
        logger.error(f"BoxIM 贴纸解析失败: {e}")
        segs.append(Seg(type="text", data="[表情]"))


async def _sticker_with_id(
    handler: Any, info: dict, sticker_id: int, sticker_name: str, segs: List[Seg]
) -> None:
    if not global_config.sticker.download_as_emoji:
        segs.append(Seg(type="text", data=sticker_name))
        return
    image_url = info.get("imageUrl") or info.get("image_url")
    if not image_url:
        image_url = await handler._get_sticker_image_url(sticker_id)
    if not image_url:
        segs.append(Seg(type="text", data=sticker_name))
        return
    try:
        segs.append(Seg(type="emoji", data=await get_image_base64(image_url)))
    except Exception as e:
        logger.error(f"下载贴纸图片失败: {e}")
        segs.append(Seg(type="text", data=sticker_name))


async def _sticker_without_id(info: dict, sticker_name: str, segs: List[Seg]) -> None:
    image_url = info.get("imageUrl") or info.get("image_url") or info.get("thumbUrl")
    if sticker_name:
        segs.append(Seg(type="text", data=sticker_name))
        return
    if image_url and global_config.sticker.download_as_emoji:
        try:
            segs.append(Seg(type="emoji", data=await get_image_base64(image_url)))
            return
        except Exception as e:
            logger.warning(f"BoxIM 贴纸无 stickerId，下载 imageUrl 失败: {e}")
    segs.append(Seg(type="text", data="[表情]"))


async def _parse_voice(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        voice_info = json.loads(content)
        url = voice_info.get("url") or voice_info.get("voice_url") or ""
        if not url:
            logger.warning("BoxIM 语音消息缺少 URL")
            return
        voice_bytes = await handler._download_url(url)
        if voice_bytes:
            segs.append(Seg(type="voice", data=base64.b64encode(voice_bytes).decode("utf-8")))
    except Exception as e:
        logger.error(f"BoxIM 语音解析失败: {e}")


async def _parse_video(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        info = json.loads(content)
        cover_url = info.get("coverUrl") or info.get("cover_url") or ""
        file_name = info.get("fileName") or info.get("file_name") or "视频"
        file_size = info.get("fileSize") or info.get("file_size") or "未知大小"
        if cover_url:
            try:
                segs.append(Seg(type="image", data=await get_image_base64(cover_url)))
            except Exception as e:
                logger.debug(f"视频封面下载失败: {e}")
        segs.append(Seg(type="text", data=f"[视频: {file_name}, 大小: {file_size}字节]"))
    except Exception as e:
        logger.error(f"BoxIM 视频解析失败: {e}")


async def _parse_file(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        info = json.loads(content)
        file_name = info.get("name") or info.get("fileName") or info.get("file_name") or "未知文件"
        file_size = info.get("size") or info.get("fileSize") or info.get("file_size") or "未知大小"
        image_exts = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
        if any(file_name.lower().endswith(ext) for ext in image_exts):
            url = info.get("url") or info.get("originUrl") or info.get("origin_url") or ""
            if url:
                segs.append(Seg(type="image", data=await get_image_base64(url)))
                return
            segs.append(Seg(type="text", data=f"[图片文件: {file_name}, 大小: {file_size}字节]"))
            return
        segs.append(Seg(type="text", data=f"[文件: {file_name}, 大小: {file_size}字节]"))
    except Exception as e:
        logger.error(f"BoxIM 文件解析失败: {e}")


async def _parse_forward(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        forward_data = json.loads(content)
        if isinstance(forward_data, dict):
            title = forward_data.get("summary") or forward_data.get("title") or "[合并转发消息]"
            segs.append(Seg(type="text", data=f"[合并转发] {title}"))
            return
        if isinstance(forward_data, list):
            for item in forward_data:
                if not isinstance(item, dict):
                    continue
                sender = item.get("sender_name") or item.get("nickname") or "未知用户"
                text = item.get("content") or item.get("text") or ""
                segs.append(Seg(type="text", data=f"【{sender}】: {text}"))
    except Exception as e:
        logger.error(f"BoxIM 合并转发解析失败: {e}")
        segs.append(Seg(type="text", data="[合并转发消息]"))


async def _parse_recall(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    is_group = bool(msg_data.get("groupId"))
    recalled_user_info = None
    if is_group and msg_data.get("sendId"):
        sender_id = msg_data.get("sendId")
        sender_name = await handler._get_real_username(sender_id, msg_data)
        recalled_user_info = UserInfo(
            platform=global_config.maibot_server.platform_name,
            user_id=sender_id,
            user_nickname=sender_name,
            user_cardname=None,
        ).to_dict()
    segs.append(
        Seg(
            type="notify",
            data={
                "sub_type": "group_recall" if is_group else "friend_recall",
                "message_id": msg_data.get("recallMessageId") or msg_data.get("id"),
                "recalled_user_info": recalled_user_info,
            },
        )
    )


async def _parse_user_card(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        info = json.loads(content)
        nick = info.get("nick_name") or info.get("nickname") or "未知用户"
        segs.append(Seg(type="text", data=f"[推荐联系人] {nick}"))
    except Exception:
        segs.append(Seg(type="text", data="[推荐联系人]"))


async def _parse_group_card(handler: Any, content: str, msg_data: dict, segs: List[Seg]) -> None:
    try:
        info = json.loads(content)
        name = info.get("group_name") or info.get("name") or "未知群聊"
        segs.append(Seg(type="text", data=f"[推荐群聊] {name}"))
    except Exception:
        segs.append(Seg(type="text", data="[推荐群聊]"))


def _build_parsers() -> Dict[int, Any]:
    from sdk import BoxIMMessageType as T

    return {
        int(T.TEXT): _parse_text,
        int(T.IMAGE): _parse_image,
        int(T.STICKER): _parse_sticker,
        int(T.VOICE): _parse_voice,
        int(T.VIDEO): _parse_video,
        int(T.FILE): _parse_file,
        int(T.MERGE_FORWARD): _parse_forward,
        int(T.RECALL): _parse_recall,
        int(T.USER_CARD): _parse_user_card,
        int(T.GROUP_CARD): _parse_group_card,
    }


_PARSERS = _build_parsers()
