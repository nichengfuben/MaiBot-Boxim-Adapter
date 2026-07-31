from __future__ import annotations

from typing import Optional

from sdk import BoxIMError, MessageType

from src.runtime.logger import logger


class ImMediaMixin:
    async def send_text(self, user_id: int, text: str, quote_message_id: Optional[int] = None) -> Optional[int]:
        """发送私聊文本，返回消息 ID"""
        try:
            result = await self.boxim_client._asend_private_message(
                user_id, text, MessageType.TEXT, quote_message_id=quote_message_id
            )
            # BoxIM API 返回的 data 中包含消息 id
            if isinstance(result, dict):
                return result.get("id")
            return None
        except BoxIMError as e:
            error_msg = e.message
            error_code = e.code
            error_type = _detect_business_error(error_msg)
            if error_type:
                logger.warning(f"发送私聊文本失败 (业务错误: {error_type}, code={error_code}): {error_msg}")
                await self._notify_business_error(user_id, None, error_type, error_msg, error_code)
            else:
                logger.error(f"发送私聊文本失败 (code={error_code}): {error_msg}")
            return None
        except Exception as e:
            logger.error(f"发送私聊文本失败: {e}")
            return None

    async def send_group_text(self, group_id: int, text: str, at_users: Optional[list] = None, quote_message_id: Optional[int] = None) -> Optional[int]:
        """发送群聊文本，返回消息 ID"""
        try:
            result = await self.boxim_client._asend_group_message(
                group_id, text, MessageType.TEXT, at_users=at_users or [], quote_message_id=quote_message_id
            )
            if isinstance(result, dict):
                return result.get("id")
            return None
        except BoxIMError as e:
            error_msg = e.message
            error_code = e.code
            error_type = _detect_business_error(error_msg)
            if error_type:
                logger.warning(f"发送群聊文本失败 (业务错误: {error_type}, code={error_code}): {error_msg}")
                await self._notify_business_error(None, group_id, error_type, error_msg, error_code)
            else:
                logger.error(f"发送群聊文本失败 (code={error_code}): {error_msg}")
            return None
        except Exception as e:
            logger.error(f"发送群聊文本失败: {e}")
            return None

    async def send_image(self, user_id: int, image_path: str) -> bool:
        """发送私聊图片"""
        try:
            await self.boxim_client.asend_image(user_id, image_path)
            return True
        except BoxIMError as e:
            logger.error(f"发送私聊图片失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送私聊图片失败: {e}")
            return False

    async def send_group_image(self, group_id: int, image_path: str, at_users: Optional[list] = None) -> bool:
        """发送群聊图片"""
        try:
            await self.boxim_client.asend_group_image(group_id, image_path, at_users)
            return True
        except BoxIMError as e:
            logger.error(f"发送群聊图片失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送群聊图片失败: {e}")
            return False

    async def send_file(self, user_id: int, file_path: str) -> bool:
        """发送私聊文件"""
        try:
            await self.boxim_client.asend_file(user_id, file_path)
            return True
        except BoxIMError as e:
            logger.error(f"发送私聊文件失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送私聊文件失败: {e}")
            return False

    async def send_group_file(self, group_id: int, file_path: str, at_users: Optional[list] = None) -> bool:
        """发送群聊文件"""
        try:
            await self.boxim_client.asend_group_file(group_id, file_path, at_users)
            return True
        except BoxIMError as e:
            logger.error(f"发送群聊文件失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送群聊文件失败: {e}")
            return False

    async def send_voice(self, user_id: int, voice_path: str, duration: int = 3) -> bool:
        """发送私聊语音"""
        try:
            await self.boxim_client.asend_voice(user_id, voice_path, duration)
            return True
        except BoxIMError as e:
            logger.error(f"发送私聊语音失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送私聊语音失败: {e}")
            return False

    async def send_group_voice(self, group_id: int, voice_path: str, duration: int = 3, at_users: Optional[list] = None) -> bool:
        """发送群聊语音"""
        try:
            await self.boxim_client.asend_group_voice(group_id, voice_path, duration, at_users)
            return True
        except BoxIMError as e:
            logger.error(f"发送群聊语音失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送群聊语音失败: {e}")
            return False

    async def send_video(self, user_id: int, video_path: str) -> bool:
        """发送私聊视频"""
        try:
            await self.boxim_client.asend_video(user_id, video_path)
            return True
        except BoxIMError as e:
            logger.error(f"发送私聊视频失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送私聊视频失败: {e}")
            return False

    async def send_group_video(self, group_id: int, video_path: str, at_users: Optional[list] = None) -> bool:
        """发送群聊视频"""
        try:
            await self.boxim_client.asend_group_video(group_id, video_path, at_users)
            return True
        except BoxIMError as e:
            logger.error(f"发送群聊视频失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"发送群聊视频失败: {e}")
            return False

    async def send_sticker(self, user_id: int, sticker_id: int) -> bool:
        """发送私聊贴纸"""
        try:
            await self.boxim_client.asend_sticker(user_id, sticker_id)
            return True
        except Exception as e:
            logger.error(f"发送私聊贴纸失败: {e}")
            return False

    async def send_group_sticker(self, group_id: int, sticker_id: int, at_users: Optional[list] = None) -> bool:
        """发送群聊贴纸"""
        try:
            await self.boxim_client.asend_group_sticker(group_id, sticker_id, at_users)
            return True
        except Exception as e:
            logger.error(f"发送群聊贴纸失败: {e}")
            return False

    async def recall_private_message(self, message_id: int) -> bool:
        """撤回私聊消息"""
        try:
            await self.boxim_client.arecall_private_message(message_id)
            return True
        except Exception as e:
            logger.error(f"撤回私聊消息失败: {e}")
            return False

    async def recall_group_message(self, message_id: int) -> bool:
        """撤回群聊消息"""
        try:
            await self.boxim_client.arecall_group_message(message_id)
            return True
        except Exception as e:
            logger.error(f"撤回群聊消息失败: {e}")
            return False

    async def recall_message(self, message_id: int, is_group: bool = True) -> bool:
        """撤回消息（自动判断私聊/群聊）"""
        if is_group:
            return await self.recall_group_message(message_id)
        else:
            return await self.recall_private_message(message_id)
