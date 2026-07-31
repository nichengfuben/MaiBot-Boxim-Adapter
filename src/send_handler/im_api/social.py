from __future__ import annotations

from typing import Optional

from sdk import BoxIMError, MessageType

from src.runtime.logger import logger


class ImSocialMixin:
    async def get_me(self) -> dict:
        """获取自身信息"""
        try:
            info = await self.boxim_client.aget_me()
            return {"id": info.get("id", 0), "nick_name": info.get("nickName", ""), "user_name": info.get("userName", "")}
        except Exception as e:
            logger.error(f"获取自身信息失败: {e}")
            return {"error": str(e)}

    async def get_user_info(self, user_id: int) -> dict:
        """获取用户信息"""
        try:
            u = await self.boxim_client.aget_user(user_id)
            return {
                "id": u.id or 0, "nick_name": u.nick_name or "",
                "user_name": u.user_name or "", "head_image": u.head_image or "",
            }
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return {"error": str(e)}

    async def search_users(self, keyword: str) -> dict:
        """搜索用户"""
        try:
            users = await self.boxim_client.asearch_users(keyword)
            result = []
            for u in users:
                result.append({
                    "id": u.id or 0, "nick_name": u.nick_name or "",
                    "user_name": u.user_name or "",
                })
            return {"users": result, "count": len(result)}
        except Exception as e:
            logger.error(f"搜索用户失败: {e}")
            return {"error": str(e)}

    # === 好友管理 ===

    async def get_friend_list(self) -> dict:
        """获取好友列表"""
        try:
            friends = await self.boxim_client.aget_friends()
            result = []
            for f in friends:
                result.append({
                    "id": f.id, "nick_name": f.nick_name or "",
                    "remark_nick_name": f.remark_nick_name or "",
                    "show_nick_name": f.show_nick_name or f.nick_name or "",
                })
            return {"friends": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取好友列表失败: {e}")
            return {"error": str(e)}

    async def add_friend(self, user_id: int, remark: str = None) -> bool:
        """添加好友"""
        try:
            await self.boxim_client.aadd_friend(user_id, remark=remark)
            return True
        except Exception as e:
            logger.error(f"添加好友失败: {e}")
            return False

    async def delete_friend(self, user_id: int) -> bool:
        """删除好友"""
        try:
            await self.boxim_client.adelete_friend(user_id)
            return True
        except Exception as e:
            logger.error(f"删除好友失败: {e}")
            return False

    # === 黑名单 ===

    async def add_to_blacklist(self, user_id: int) -> bool:
        """添加到黑名单"""
        try:
            await self.boxim_client.aadd_to_blacklist(user_id)
            return True
        except Exception as e:
            logger.error(f"添加到黑名单失败: {e}")
            return False

    async def remove_from_blacklist(self, user_id: int) -> bool:
        """从黑名单移除"""
        try:
            await self.boxim_client.aremove_from_blacklist(user_id)
            return True
        except Exception as e:
            logger.error(f"从黑名单移除失败: {e}")
            return False

    async def get_blacklist(self) -> dict:
        """获取黑名单"""
        try:
            users = await self.boxim_client.aget_blacklist()
            result = []
            for u in users:
                result.append({
                    "id": u.id, "nick_name": u.nick_name or "",
                    "user_name": u.user_name or "",
                })
            return {"users": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取黑名单失败: {e}")
            return {"error": str(e)}

    # === 群在线成员 ===

    async def get_group_online_members(self, group_id: int) -> dict:
        """获取群在线成员"""
        try:
            members = await self.boxim_client.aget_group_online_members(group_id)
            return {"members": members, "count": len(members)}
        except Exception as e:
            logger.error(f"获取群在线成员失败: {e}")
            return {"error": str(e)}


    # === 群踢人（映射到 remove_group_members） ===

    async def kick_group_member(self, group_id: int, user_id: int) -> bool:
        """踢出群成员（映射到 remove_group_members）"""
        try:
            await self.boxim_client.aremove_group_members(group_id, [user_id])
            return True
        except Exception as e:
            logger.error(f"踢出群成员失败: {e}")
            return False

    async def kick_group_members(self, group_id: int, user_ids: list) -> bool:
        """批量踢出群成员"""
        try:
            await self.boxim_client.aremove_group_members(group_id, user_ids)
            return True
        except Exception as e:
            logger.error(f"批量踢出群成员失败: {e}")
            return False

    # === 好友设置 ===

    async def set_friend_dnd(self, user_id: int, dnd: bool) -> bool:
        """设置好友免打扰"""
        try:
            await self.boxim_client.aset_friend_dnd(user_id, dnd)
            return True
        except Exception as e:
            logger.error(f"设置好友免打扰失败: {e}")
            return False

    async def set_friend_top(self, user_id: int, top: bool) -> bool:
        """设置好友置顶"""
        try:
            await self.boxim_client.aset_friend_top(user_id, top)
            return True
        except Exception as e:
            logger.error(f"设置好友置顶失败: {e}")
            return False

    async def update_friend_remark(self, user_id: int, remark: str) -> bool:
        """更新好友备注"""
        try:
            await self.boxim_client.aupdate_friend_remark(user_id, remark)
            return True
        except Exception as e:
            logger.error(f"更新好友备注失败: {e}")
            return False

    # === 好友信息查询 ===

    async def get_friend_info(self, user_id: int) -> dict:
        """获取好友详细信息"""
        try:
            f = await self.boxim_client.aget_friend_info(user_id)
            return {
                "id": f.id, "nick_name": f.nick_name or "",
                "remark_nick_name": f.remark_nick_name or "",
                "is_dnd": f.is_dnd, "is_top": f.is_top,
                "online": f.online,
            }
        except Exception as e:
            logger.error(f"获取好友信息失败: {e}")
            return {"error": str(e)}

    # === 好友请求 ===

    async def get_friend_requests(self) -> dict:
        """获取好友请求列表"""
        try:
            reqs = await self.boxim_client.aget_friend_requests()
            result = []
            for r in reqs:
                result.append({
                    "id": r.id,
                    "req_user_id": r.req_user_id,
                    "req_user_nick_name": r.req_user_nick_name or "",
                    "req_user_name": r.req_user_name or "",
                    "status": int(r.status) if r.status else 0,
                    "message": r.message or "",
                })
            return {"requests": result, "count": len(result)}
        except Exception as e:
            logger.error(f"获取好友请求失败: {e}")
            return {"error": str(e)}

    async def accept_friend_request(self, request_id: int) -> bool:
        """接受好友请求"""
        try:
            await self.boxim_client.aaccept_friend_request(request_id)
            return True
        except Exception as e:
            logger.error(f"接受好友请求失败: {e}")
            return False

    async def reject_friend_request(self, request_id: int) -> bool:
        """拒绝好友请求"""
        try:
            await self.boxim_client.areject_friend_request(request_id)
            return True
        except Exception as e:
            logger.error(f"拒绝好友请求失败: {e}")
            return False

    async def recall_friend_request(self, request_id: int) -> bool:
        """撤回好友请求"""
        try:
            await self.boxim_client.arecall_friend_request(request_id)
            return True
        except Exception as e:
            logger.error(f"撤回好友请求失败: {e}")
            return False
