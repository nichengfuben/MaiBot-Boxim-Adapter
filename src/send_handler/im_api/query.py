from __future__ import annotations

from typing import Optional

from sdk import BoxIMError, MessageType

from src.runtime.logger import logger


class ImQueryMixin:
    async def delete_private_messages(self, chat_id: int, message_ids: list) -> bool:
        """删除私聊消息"""
        try:
            await self.boxim_client.adelete_private_messages(chat_id, message_ids)
            return True
        except Exception as e:
            logger.error(f"删除私聊消息失败: {e}")
            return False

    async def delete_group_messages(self, chat_id: int, message_ids: list) -> bool:
        """删除群聊消息"""
        try:
            await self.boxim_client.adelete_group_messages(chat_id, message_ids)
            return True
        except Exception as e:
            logger.error(f"删除群聊消息失败: {e}")
            return False

    async def delete_private_chat(self, chat_id: int) -> bool:
        """清空私聊记录"""
        try:
            await self.boxim_client.adelete_private_chat(chat_id)
            return True
        except Exception as e:
            logger.error(f"清空私聊记录失败: {e}")
            return False

    async def delete_group_chat(self, chat_id: int) -> bool:
        """清空群聊记录"""
        try:
            await self.boxim_client.adelete_group_chat(chat_id)
            return True
        except Exception as e:
            logger.error(f"清空群聊记录失败: {e}")
            return False

    async def get_private_message_history(self, friend_id: int, min_seq_no: int = None, max_seq_no: int = None) -> dict:
        """获取私聊历史消息"""
        try:
            kwargs = {}
            if min_seq_no is not None:
                kwargs["min_seq_no"] = min_seq_no
            if max_seq_no is not None:
                kwargs["max_seq_no"] = max_seq_no
            messages = await self.boxim_client.aget_private_message_history(friend_id, **kwargs)
            return {"messages": messages, "count": len(messages)}
        except Exception as e:
            logger.error(f"获取私聊历史消息失败: {e}")
            return {"error": str(e)}

    async def get_group_message_history(self, group_id: int, min_seq_no: int = None, max_seq_no: int = None) -> dict:
        """获取群聊历史消息"""
        try:
            kwargs = {}
            if min_seq_no is not None:
                kwargs["min_seq_no"] = min_seq_no
            if max_seq_no is not None:
                kwargs["max_seq_no"] = max_seq_no
            messages = await self.boxim_client.aget_group_message_history(group_id, **kwargs)
            return {"messages": messages, "count": len(messages)}
        except Exception as e:
            logger.error(f"获取群聊历史消息失败: {e}")
            return {"error": str(e)}

    async def mark_private_read(self, friend_id: int, message_id: int = None) -> bool:
        """标记私聊已读"""
        try:
            await self.boxim_client.amark_private_read(friend_id, message_id=message_id)
            return True
        except Exception as e:
            logger.error(f"标记私聊已读失败: {e}")
            return False

    async def mark_group_read(self, group_id: int, message_id: int = None) -> bool:
        """标记群聊已读"""
        try:
            await self.boxim_client.amark_group_read(group_id, message_id=message_id)
            return True
        except Exception as e:
            logger.error(f"标记群聊已读失败: {e}")
            return False

    async def get_group_message_readers(self, group_id: int, message_id: int) -> dict:
        """获取群消息已读用户"""
        try:
            readers = await self.boxim_client.aget_group_message_readers(group_id, message_id)
            return {"readers": readers, "count": len(readers)}
        except Exception as e:
            logger.error(f"获取已读用户失败: {e}")
            return {"error": str(e)}

    # === 离线消息 ===

    async def load_private_offline_message(self, min_id: int = 0) -> dict:
        """拉取私聊离线消息"""
        try:
            messages = await self.boxim_client.aload_private_offline_message(min_id)
            return {"messages": messages, "count": len(messages)}
        except Exception as e:
            logger.error(f"拉取私聊离线消息失败: {e}")
            return {"error": str(e)}

    async def load_group_offline_message(self, min_id: int = 0) -> dict:
        """拉取群聊离线消息"""
        try:
            messages = await self.boxim_client.aload_group_offline_message(min_id)
            return {"messages": messages, "count": len(messages)}
        except Exception as e:
            logger.error(f"拉取群聊离线消息失败: {e}")
            return {"error": str(e)}

    async def load_system_offline_message(self, min_seq_no: int = 0) -> dict:
        """拉取系统离线消息"""
        try:
            messages = await self.boxim_client.aload_system_offline_message(min_seq_no)
            result = []
            for m in messages:
                result.append({
                    "seq_no": m.seq_no, "type": m.type, "content": m.content,
                })
            return {"messages": result, "count": len(result)}
        except Exception as e:
            logger.error(f"拉取系统离线消息失败: {e}")
            return {"error": str(e)}

    # === 贴纸/表情包 ===

    async def get_sticker_albums(self) -> dict:
        """获取表情包专辑列表"""
        try:
            albums = await self.boxim_client.aget_sticker_albums()
            result = []
            for a in albums:
                result.append({
                    "id": a.id, "name": a.name, "sticker_count": a.sticker_count,
                })
            return {"albums": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取表情包专辑失败: {e}")
            return {"error": str(e)}

    async def get_stickers(self, album_id: int) -> dict:
        """获取专辑贴纸列表"""
        try:
            stickers = await self.boxim_client.aget_stickers(album_id)
            result = []
            for s in stickers:
                result.append({
                    "id": s.id, "name": s.name, "image_url": s.image_url,
                })
            return {"stickers": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取贴纸列表失败: {e}")
            return {"error": str(e)}

    async def search_stickers(self, name: str) -> dict:
        """搜索贴纸"""
        try:
            stickers = await self.boxim_client.asearch_stickers(name)
            result = []
            for s in stickers:
                result.append({
                    "id": s.id, "name": s.name, "image_url": s.image_url,
                })
            return {"stickers": result, "count": len(result)}
        except Exception as e:
            logger.error(f"搜索贴纸失败: {e}")
            return {"error": str(e)}

    async def get_custom_stickers(self) -> dict:
        """获取自定义贴纸"""
        try:
            stickers = await self.boxim_client.aget_custom_stickers()
            result = []
            for s in stickers:
                result.append({
                    "id": s.id, "name": s.name, "image_url": s.image_url,
                })
            return {"stickers": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取自定义贴纸失败: {e}")
            return {"error": str(e)}

    async def add_custom_sticker(self, name: str, image_url: str, thumb_url: str, width: int = 100, height: int = 100) -> bool:
        """添加自定义贴纸"""
        try:
            await self.boxim_client.aadd_custom_sticker(name, image_url, thumb_url, width, height)
            return True
        except Exception as e:
            logger.error(f"添加自定义贴纸失败: {e}")
            return False

    async def delete_custom_sticker(self, sticker_id: int) -> bool:
        """删除自定义贴纸"""
        try:
            await self.boxim_client.adelete_custom_sticker(sticker_id)
            return True
        except Exception as e:
            logger.error(f"删除自定义贴纸失败: {e}")
            return False

    async def top_custom_sticker(self, sticker_id: int) -> bool:
        """置顶自定义贴纸"""
        try:
            await self.boxim_client.atop_custom_sticker(sticker_id)
            return True
        except Exception as e:
            logger.error(f"置顶自定义贴纸失败: {e}")
            return False

    # === 投诉举报 ===

    async def submit_complaint(self, target_type: str, target_id: int, complaint_type: int, content: str, target_name: str = "", images: list = None) -> dict:
        """提交投诉"""
        try:
            result = await self.boxim_client.asubmit_complaint(
                target_type=target_type, target_id=target_id,
                complaint_type=complaint_type, content=content,
                target_name=target_name, images=images or [],
            )
            return {"success": True}
        except Exception as e:
            logger.error(f"提交投诉失败: {e}")
            return {"error": str(e)}

    # === 系统消息 ===

    async def mark_system_read(self, max_seq_no: int) -> bool:
        """标记系统消息已读"""
        try:
            await self.boxim_client.amark_system_read(max_seq_no)
            return True
        except Exception as e:
            logger.error(f"标记系统消息已读失败: {e}")
            return False

    async def get_system_message_content(self, message_id: int) -> dict:
        """获取系统消息内容"""
        try:
            result = await self.boxim_client.aget_system_message_content(message_id)
            return result if isinstance(result, dict) else {"content": str(result)}
        except Exception as e:
            logger.error(f"获取系统消息内容失败: {e}")
            return {"error": str(e)}

    # === 个人资料 ===

    async def update_profile(self, **kwargs) -> bool:
        """更新个人资料（signature/nickName/sex/headImage 等）"""
        try:
            await self.boxim_client.aupdate_profile(**kwargs)
            return True
        except BoxIMError as e:
            logger.error(f"更新个人资料失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"更新个人资料失败: {e}")
            return False

    # === 实名认证 ===

    async def get_realname_auth_info(self) -> dict:
        """获取实名认证信息"""
        try:
            return await self.boxim_client.aget_realname_auth_info()
        except Exception as e:
            logger.error(f"获取实名认证信息失败: {e}")
            return {"error": str(e)}

    async def submit_realname_auth(self, real_name: str, id_card: str) -> bool:
        """提交实名认证"""
        try:
            await self.boxim_client.asubmit_realname_auth(real_name, id_card)
            return True
        except BoxIMError as e:
            logger.error(f"提交实名认证失败 (code={e.code}): {e.message}")
            return False
        except Exception as e:
            logger.error(f"提交实名认证失败: {e}")
            return False
