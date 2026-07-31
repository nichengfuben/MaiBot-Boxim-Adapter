from __future__ import annotations

from typing import Any, Optional
import os
import base64
import tempfile

from maim_message import MessageBase

from src.runtime.logger import logger
from src.send_handler.im_sending import boxim_message_sender


def _extract_quote_id(segments: list) -> Optional[int]:
    for seg in segments:
        if seg.get("type") != "reply":
            continue
        reply_data = seg.get("data", {})
        raw = reply_data.get("id") if isinstance(reply_data, dict) else reply_data
        return int(raw) if raw else None
    return None


def _collect_at_users(segments: list) -> list:
    at_users = []
    for seg in segments:
        if seg.get("type") != "at":
            continue
        uid = seg.get("data", {}).get("user_id")
        if uid is not None:
            at_users.append(int(uid))
    return at_users


class OutboundMixin:
    async def _send_private_messages(
        self, user_id: int, segments: list, original_message_base: MessageBase = None
    ) -> bool:
        quote_message_id = _extract_quote_id(segments)
        for seg in segments:
            await self._send_one_private(user_id, seg, quote_message_id, original_message_base)
            if seg.get("type") == "text":
                quote_message_id = None
        return True

    async def _send_one_private(self, user_id, seg, quote_message_id, original_message_base):
        seg_type = seg.get("type")
        seg_data = seg.get("data", {})
        if seg_type == "text":
            sent = await boxim_message_sender.send_text(
                user_id, seg_data.get("text", ""), quote_message_id
            )
            if sent and original_message_base:
                await self._send_message_id_echo(original_message_base, sent)
            return
        if seg_type == "reply":
            return
        if seg_type in ("image", "emoji", "voice", "video", "file"):
            kind = "image" if seg_type == "emoji" else seg_type
            ok = await self._handle_file_send(seg_data.get("file", ""), kind, user_id, False)
            if not ok:
                logger.warning(f"私聊{seg_type}发送失败")
            return
        if seg_type == "face" and seg_data.get("id") is not None:
            try:
                await boxim_message_sender.send_sticker(user_id, int(seg_data["id"]))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid face_id: {e}")
            return
        logger.warning(f"Unsupported private segment: {seg_type}")

    async def _send_group_messages(
        self, group_id: int, segments: list, original_message_base: MessageBase = None
    ) -> bool:
        at_users = _collect_at_users(segments)
        quote_message_id = _extract_quote_id(segments)
        for seg in segments:
            await self._send_one_group(
                group_id, seg, at_users, quote_message_id, original_message_base
            )
            if seg.get("type") == "text":
                quote_message_id = None
        return True

    async def _send_one_group(
        self, group_id, seg, at_users, quote_message_id, original_message_base
    ):
        seg_type = seg.get("type")
        seg_data = seg.get("data", {})
        if seg_type in ("at", "reply"):
            return
        if seg_type == "text":
            sent = await boxim_message_sender.send_group_text(
                group_id, seg_data.get("text", ""), at_users or None, quote_message_id
            )
            if sent and original_message_base:
                await self._send_message_id_echo(original_message_base, sent)
            return
        if seg_type in ("image", "emoji", "voice", "video", "file"):
            kind = "image" if seg_type == "emoji" else seg_type
            ok = await self._handle_file_send(seg_data.get("file", ""), kind, group_id, True)
            if not ok:
                logger.warning(f"群聊{seg_type}发送失败")
            return
        if seg_type == "face" and seg_data.get("id") is not None:
            try:
                await boxim_message_sender.send_group_sticker(group_id, int(seg_data["id"]))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid face_id: {e}")
            return
        logger.warning(f"Unsupported group segment: {seg_type}")

    async def _handle_file_send(self, file_path: str, file_type: str, target_id: int, is_group: bool):
        if not file_path:
            return False
        if file_path.startswith("base64://"):
            return await self._send_base64_file(file_path, file_type, target_id, is_group)
        if os.path.isfile(file_path):
            return await self._send_local_file(file_path, file_type, target_id, is_group)
        if file_path.startswith(("http://", "https://")):
            return await self._send_url_file(file_path, file_type, target_id, is_group)
        logger.warning(f"未知文件路径格式: {file_path[:80]}")
        return False

    async def _send_base64_file(self, file_path, file_type, target_id, is_group):
        try:
            raw = base64.b64decode(file_path[len("base64://"):])
            suffix = self._get_file_extension(file_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            try:
                return await self._send_local_file(tmp_path, file_type, target_id, is_group)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            logger.error(f"base64 文件发送失败: {e}")
            return False

    async def _send_local_file(self, file_path, file_type, target_id, is_group):
        try:
            senders = {
                ("image", False): boxim_message_sender.send_image,
                ("voice", False): boxim_message_sender.send_voice,
                ("video", False): boxim_message_sender.send_video,
                ("file", False): boxim_message_sender.send_file,
                ("image", True): boxim_message_sender.send_group_image,
                ("voice", True): boxim_message_sender.send_group_voice,
                ("video", True): boxim_message_sender.send_group_video,
                ("file", True): boxim_message_sender.send_group_file,
            }
            fn = senders.get((file_type, is_group))
            if not fn:
                return False
            return await fn(target_id, file_path)
        except Exception as e:
            logger.error(f"本地文件发送失败: {e}")
            return False

    async def _send_url_file(self, file_path, file_type, target_id, is_group):
        from src.runtime.utils import download_url
        try:
            data = await download_url(file_path)
            if not data:
                return False
            suffix = self._get_file_extension(file_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            try:
                return await self._send_local_file(tmp_path, file_type, target_id, is_group)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            logger.error(f"URL 文件发送失败: {e}")
            return False

    def _get_file_extension(self, file_type: str) -> str:
        return {"image": ".jpg", "voice": ".mp3", "video": ".mp4", "file": ".bin"}.get(
            file_type, ".bin"
        )
