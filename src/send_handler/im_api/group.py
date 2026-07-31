from __future__ import annotations

from typing import Optional

from sdk import BoxIMError, MessageType

from src.runtime.logger import logger


class ImGroupMixin:
    async def set_group_muted(self, group_id: int, muted: bool) -> bool:
        """设置群全员禁言"""
        try:
            await self.boxim_client.aset_group_muted(group_id, muted)
            return True
        except Exception as e:
            logger.error(f"设置群全员禁言失败: {e}")
            return False

    async def modify_group(self, group_id: int, **kwargs) -> bool:
        """修改群信息"""
        try:
            await self.boxim_client.amodify_group(group_id, **kwargs)
            return True
        except Exception as e:
            logger.error(f"修改群信息失败: {e}")
            return False

    async def delete_group(self, group_id: int) -> bool:
        """解散群"""
        try:
            await self.boxim_client.adelete_group(group_id)
            return True
        except Exception as e:
            logger.error(f"解散群失败: {e}")
            return False

    async def quit_group(self, group_id: int) -> bool:
        """退群"""
        try:
            await self.boxim_client.aquit_group(group_id)
            return True
        except Exception as e:
            logger.error(f"退群失败: {e}")
            return False

    # === 群组查询 ===

    async def get_group_info(self, group_id: int) -> dict:
        """获取群信息"""
        try:
            g = await self.boxim_client.aget_group_info(group_id)
            return {
                "id": g.id, "name": g.name, "owner_id": g.owner_id,
                "notice": g.notice, "member_count": g.member_count,
                "is_muted": g.is_muted, "is_dnd": g.is_dnd,
                "is_allow_invite": g.is_allow_invite,
                "is_allow_share_card": g.is_allow_share_card,
                "head_image": g.head_image,
            }
        except Exception as e:
            logger.error(f"获取群信息失败: {e}")
            return {"error": str(e)}

    async def get_groups(self) -> dict:
        """获取群列表"""
        try:
            groups = await self.boxim_client.aget_groups()
            result = []
            for g in groups:
                result.append({
                    "id": g.id, "name": g.name, "member_count": g.member_count,
                })
            return {"groups": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取群列表失败: {e}")
            return {"error": str(e)}

    async def get_group_members(self, group_id: int) -> dict:
        """获取群成员列表"""
        try:
            members = await self.boxim_client.aget_group_members(group_id)
            result = []
            for m in members:
                result.append({
                    "id": m.id, "user_name": m.user_name or "",
                    "nick_name": m.nick_name or "",
                })
            return {"members": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取群成员列表失败: {e}")
            return {"error": str(e)}

    # === 群组管理 ===

    async def create_group(self, name: str, member_ids: list = None) -> dict:
        """创建群（boxim-sdk 3.2+：创建仅传名称，成员需再邀请）。"""
        try:
            g = await self.boxim_client.acreate_group(name)
            if member_ids:
                await self.boxim_client.ainvite_to_group(g.id, member_ids)
            return {"id": g.id, "name": g.name}
        except Exception as e:
            logger.error(f"创建群失败: {e}")
            return {"error": str(e)}

    async def join_group(self, group_id: int, token: str = None) -> bool:
        """加入群"""
        try:
            await self.boxim_client.ajoin_group(group_id, token)
            return True
        except Exception as e:
            logger.error(f"加入群失败: {e}")
            return False

    async def invite_to_group(self, group_id: int, user_ids: list) -> bool:
        """邀请用户入群"""
        try:
            await self.boxim_client.ainvite_to_group(group_id, user_ids)
            return True
        except Exception as e:
            logger.error(f"邀请用户入群失败: {e}")
            return False

    async def remove_group_members(self, group_id: int, user_ids: list) -> bool:
        """移除群成员"""
        try:
            await self.boxim_client.aremove_group_members(group_id, user_ids)
            return True
        except Exception as e:
            logger.error(f"移除群成员失败: {e}")
            return False

    # === 禁言管理 ===

    async def set_group_member_muted(self, group_id: int, user_ids: list, muted: bool) -> bool:
        """设置群成员禁言"""
        try:
            await self.boxim_client.aset_group_member_muted(group_id, user_ids, muted)
            return True
        except Exception as e:
            logger.error(f"设置群成员禁言失败: {e}")
            return False

    # === 群设置 ===

    async def set_group_dnd(self, group_id: int, dnd: bool) -> bool:
        """设置群免打扰"""
        try:
            await self.boxim_client.aset_group_dnd(group_id, dnd)
            return True
        except Exception as e:
            logger.error(f"设置群免打扰失败: {e}")
            return False

    async def set_group_top(self, group_id: int, top: bool) -> bool:
        """设置群置顶"""
        try:
            await self.boxim_client.aset_group_top(group_id, top)
            return True
        except Exception as e:
            logger.error(f"设置群置顶失败: {e}")
            return False

    async def set_group_allow_invite(self, group_id: int, allow: bool) -> bool:
        """设置允许成员邀请"""
        try:
            await self.boxim_client.aset_group_allow_invite(group_id, allow)
            return True
        except Exception as e:
            logger.error(f"设置允许成员邀请失败: {e}")
            return False

    async def set_group_allow_share_card(self, group_id: int, allow: bool) -> bool:
        """设置允许分享名片"""
        try:
            await self.boxim_client.aset_group_allow_share_card(group_id, allow)
            return True
        except Exception as e:
            logger.error(f"设置允许分享名片失败: {e}")
            return False

    # === 群管理 ===

    async def add_group_manager(self, group_id: int, user_ids: list) -> bool:
        """添加群管理"""
        try:
            await self.boxim_client.aadd_group_manager(group_id, user_ids)
            return True
        except Exception as e:
            logger.error(f"添加群管理失败: {e}")
            return False

    async def remove_group_manager(self, group_id: int, user_ids: list) -> bool:
        """移除群管理"""
        try:
            await self.boxim_client.aremove_group_manager(group_id, user_ids)
            return True
        except Exception as e:
            logger.error(f"移除群管理失败: {e}")
            return False

    # === 置顶消息 ===

    async def set_group_top_message(self, group_id: int, message_id: int) -> bool:
        """置顶群消息"""
        try:
            await self.boxim_client.aset_group_top_message(group_id, message_id)
            return True
        except Exception as e:
            logger.error(f"置顶群消息失败: {e}")
            return False

    async def remove_group_top_message(self, group_id: int) -> bool:
        """取消置顶"""
        try:
            await self.boxim_client.aremove_group_top_message(group_id)
            return True
        except Exception as e:
            logger.error(f"取消置顶失败: {e}")
            return False

    async def hide_group_top_message(self, group_id: int) -> bool:
        """隐藏置顶（仅自己）"""
        try:
            await self.boxim_client.ahide_group_top_message(group_id)
            return True
        except Exception as e:
            logger.error(f"隐藏置顶失败: {e}")
            return False
