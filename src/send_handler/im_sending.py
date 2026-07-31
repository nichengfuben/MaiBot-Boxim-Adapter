from typing import Optional

from sdk import BoxIMError, MessageType

from src.logger import logger


# 业务错误关键词映射
_BUSINESS_ERROR_KEYWORDS = {
    "您已不是对方好友": "friend_removed",
    "您已被禁言": "group_muted",
    "您已被踢出群聊": "group_kicked",
    "群不存在": "group_not_found",
    "用户不存在": "user_not_found",
}


def _detect_business_error(error_message: str) -> Optional[str]:
    """从错误消息中检测业务错误类型。

    Args:
        error_message: 错误消息字符串

    Returns:
        业务错误类型，如果不是业务错误则返回 None
    """
    for keyword, error_type in _BUSINESS_ERROR_KEYWORDS.items():
        if keyword in error_message:
            return error_type
    return None


class BoxIMMessageSender:
    """BoxIM SDK 消息发送器，封装所有 BoxIM 操作"""

    def __init__(self):
        self.boxim_client = None

    def set_boxim_client(self, client):
        """设置 BoxIM SDK 实例"""
        self.boxim_client = client

    async def _notify_business_error(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
        error_type: str,
        error_message: str,
        error_code: Optional[int] = None,
    ) -> None:
        """向 Bot 发送业务错误通知（作为文本消息进入模型上下文）。

        业务错误描述会作为普通文本消息发送给 Bot，经过 SessionMessage.process() 后
        生成 processed_plain_text，从而出现在 LLM 的上下文中，让模型能够感知到
        "好友已删除"、"被禁言" 等业务状态。

        Args:
            user_id: 目标用户 ID（私聊场景）
            group_id: 目标群 ID（群聊场景）
            error_type: 业务错误类型（friend_removed, group_muted 等）
            error_message: 原始错误消息
            error_code: BoxIM API 返回的业务错误码
        """
        import json
        import time
        from maim_message import FormatInfo, UserInfo, GroupInfo, Seg, BaseMessageInfo, MessageBase, SenderInfo
        from src.recv_handler.message_sending import message_send_instance
        from src.config import global_config

        platform_name = global_config.maibot_server.platform_name

        # 错误类型映射为模型可理解的描述文本
        error_descriptions = {
            "friend_removed": "（系统提示：你尝试向用户发送消息时，平台返回了好友关系异常的错误。该消息可能未送达，建议先确认好友关系是否正常。）",
            "group_muted": "（系统提示：你尝试在群聊中发送消息失败，因为你已被该群禁言。你可能需要在回复中注意这一点。）",
            "group_kicked": "（系统提示：你已被该群踢出，无法继续发送消息。）",
            "group_not_found": "（系统提示：目标群聊不存在，无法发送消息。）",
            "user_not_found": "（系统提示：目标用户不存在，无法发送消息。）",
        }

        description = error_descriptions.get(error_type, "（系统提示：业务操作失败。）")

        # 补充具体信息到描述中
        if user_id:
            description = description.replace("用户", f"用户（ID: {user_id}）")
        if group_id:
            description = description.replace("群聊", f"群聊（ID: {group_id}）")

        # 在描述末尾附加错误码，便于排查
        if error_code is not None:
            description += f"（错误码: {error_code}）"

        # 构建文本 segment，直接输出错误描述，让模型能够理解
        seg = Seg(
            type="text",
            data=description,
        )

        # 构建用户信息（使用 "系统" 作为通知消息的发送者）
        user_info = UserInfo(
            platform=platform_name,
            user_id=user_id or 0,
            user_nickname="系统",
            user_cardname=None,
        )

        # 构建群信息（群聊场景）
        group_info = None
        if group_id:
            group_info = GroupInfo(
                platform=platform_name,
                group_id=group_id,
                group_name="",
            )

        message_info = BaseMessageInfo(
            platform=platform_name,
            message_id="notice",
            time=time.time(),
            user_info=user_info,
            group_info=group_info,
            sender_info=SenderInfo(
                group_info=group_info,
                user_info=user_info,
            ),
            template_info=None,
            format_info=FormatInfo(
                content_format=["text"],
                accept_format=["text", "image", "emoji", "reply", "voice", "command", "voiceurl", "music", "videourl", "file", "imageurl", "forward", "video"],
            ),
            additional_config={
                # 在 additional_config 中保留结构化错误信息，供插件或后续逻辑使用
                "business_error": {
                    "error_type": error_type,
                    "error_message": error_message,
                    "error_code": error_code,
                    "user_id": user_id,
                    "group_id": group_id,
                },
            },
        )

        message_base = MessageBase(
            message_info=message_info,
            message_segment=seg,
            raw_message=json.dumps({
                "error_type": error_type,
                "error_message": error_message,
                "error_code": error_code,
                "description": description,
                "user_id": user_id,
                "group_id": group_id,
            }, ensure_ascii=False),
        )

        try:
            await message_send_instance.message_send(message_base)
            logger.debug(f"已发送业务错误通知: {error_type}")
        except Exception as e:
            logger.error(f"发送业务错误通知失败: {e}")

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

    # === 用户查询 ===

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

    # === 消息操作 ===

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


boxim_message_sender = BoxIMMessageSender()
