from typing import Any, Dict, Optional
import time
import os
import base64
import tempfile
from maim_message import (
    UserInfo,
    GroupInfo,
    Seg,
    BaseMessageInfo,
    MessageBase,
    ReceiverInfo,
    SenderInfo,
)
from src.logger import logger
from .send_command_handler import SendCommandHandleClass
from .send_message_handler import SendMessageHandleClass
from .im_sending import boxim_message_sender
from src.recv_handler.message_sending import message_send_instance


class SendHandler:
    def __init__(self):
        pass

    @staticmethod
    def _extract_target_info(message_info: BaseMessageInfo) -> tuple:
        """从 message_info 中提取目标 group_info 和 user_info。

        新 API 将用户/群组信息放入 receiver_info（Bot 发送场景）或 sender_info（接收场景），
        此处优先检查 receiver_info，再回退到直接字段和 sender_info。

        Returns:
            tuple: (group_info, user_info)
        """
        group_info = None
        user_info = None

        # 新 API 发送场景：目标信息在 receiver_info 中
        if message_info.receiver_info:
            group_info = message_info.receiver_info.group_info
            user_info = message_info.receiver_info.user_info

        # 回退到直接字段（旧 API 兼容）
        if not group_info and message_info.group_info:
            group_info = message_info.group_info
        if not user_info and message_info.user_info:
            user_info = message_info.user_info

        # 回退到 sender_info（接收场景）
        if not group_info and message_info.sender_info:
            group_info = message_info.sender_info.group_info
        if not user_info and message_info.sender_info:
            user_info = message_info.sender_info.user_info

        return group_info, user_info

    async def _send_message_id_echo(self, original_message_base: MessageBase, actual_id: int) -> None:
        """回传消息 ID 给 MaiBot，用于消息关联"""
        platform = original_message_base.message_info.platform
        mmc_message_id = original_message_base.message_info.message_id
        echo_data = {
            "type": "echo",
            "echo": mmc_message_id,
            "actual_id": actual_id,
        }
        try:
            await message_send_instance.send_custom_message(echo_data, platform, "message_id_echo")
            logger.debug(f"已回送消息ID: mmc={mmc_message_id}, actual={actual_id}")
        except Exception as e:
            logger.error(f"回送消息ID失败: {e}")

    async def handle_message(self, raw_message_base_dict: dict) -> None:
        raw_message_base: MessageBase = MessageBase.from_dict(raw_message_base_dict)
        message_segment: Seg = raw_message_base.message_segment
        logger.info("Received message from MaiBot, processing")
        if message_segment.type == "command":
            return await self.send_command(raw_message_base)
        else:
            return await self.send_normal_message(raw_message_base)

    async def send_command(self, raw_message_base: MessageBase) -> None:
        """Handle command messages"""
        logger.info("Processing command")
        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info, _ = self._extract_target_info(message_info)
        seg_data: Dict[str, Any] = message_segment.data
        command_name = seg_data.get('name', 'UNKNOWN')

        try:
            command, params_dict = SendCommandHandleClass.handle_command(seg_data, group_info)
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error=str(e)
            )
            return

        if not command or not params_dict:
            logger.error("Command or params missing")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error="Command or params missing"
            )
            return

        # Handle query commands that return data
        if command in ["get_login_info", "get_group_info", "get_group_list", "get_group_member_list",
                       "get_me", "get_user_info", "search_users",
                       "get_friend_list", "get_friend_info", "get_friend_requests",
                       "get_blacklist", "get_group_online_members", "get_group_message_readers",
                       "get_private_message_history", "get_group_message_history",
                       "load_private_offline_message", "load_group_offline_message", "load_system_offline_message",
                       "get_sticker_albums", "get_stickers", "search_stickers", "get_custom_stickers",
                       "get_system_message_content", "submit_complaint", "get_realname_auth_info"]:
            result = await self._execute_query_command(command, params_dict)

            if result and "error" in result:
                logger.warning(f"Query command {command_name} failed: {result['error']}")
                await self._send_command_response(
                    platform=message_info.platform,
                    command_name=command_name,
                    success=False,
                    error=result["error"],
                )
            else:
                logger.info(f"Query command {command_name} executed successfully")
                await self._send_command_response(
                    platform=message_info.platform,
                    command_name=command_name,
                    success=True,
                    data=result,
                )
            return

        # Execute other commands via BoxIM SDK
        success = await self._execute_command(command, params_dict)

        if success:
            logger.info(f"Command {command_name} executed successfully")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=True,
            )
        else:
            logger.warning(f"Command {command_name} failed")
            await self._send_command_response(
                platform=message_info.platform,
                command_name=command_name,
                success=False,
                error="BoxIM SDK execution failed",
            )

    async def _execute_query_command(self, command: str, params: Dict) -> Dict:
        """Execute a query command that returns data"""
        try:
            if command == "get_login_info":
                return await boxim_message_sender.get_me()
            elif command == "get_group_info":
                return await boxim_message_sender.get_group_info(params["group_id"])
            elif command == "get_group_list":
                return await boxim_message_sender.get_groups()
            elif command == "get_group_member_list":
                return await boxim_message_sender.get_group_members(params["group_id"])
            elif command == "get_me":
                return await boxim_message_sender.get_me()
            elif command == "get_user_info":
                return await boxim_message_sender.get_user_info(params["user_id"])
            elif command == "search_users":
                return await boxim_message_sender.search_users(params["keyword"])
            elif command == "get_friend_list":
                return await boxim_message_sender.get_friend_list()
            elif command == "get_friend_info":
                return await boxim_message_sender.get_friend_info(params["user_id"])
            elif command == "get_friend_requests":
                return await boxim_message_sender.get_friend_requests()
            elif command == "get_blacklist":
                return await boxim_message_sender.get_blacklist()
            elif command == "get_group_online_members":
                return await boxim_message_sender.get_group_online_members(params["group_id"])
            elif command == "get_group_message_readers":
                return await boxim_message_sender.get_group_message_readers(params["group_id"], params["message_id"])
            elif command == "get_private_message_history":
                return await boxim_message_sender.get_private_message_history(
                    params["friend_id"], params.get("min_seq_no"), params.get("max_seq_no"))
            elif command == "get_group_message_history":
                return await boxim_message_sender.get_group_message_history(
                    params["group_id"], params.get("min_seq_no"), params.get("max_seq_no"))
            elif command == "load_private_offline_message":
                return await boxim_message_sender.load_private_offline_message(params.get("min_id", 0))
            elif command == "load_group_offline_message":
                return await boxim_message_sender.load_group_offline_message(params.get("min_id", 0))
            elif command == "load_system_offline_message":
                return await boxim_message_sender.load_system_offline_message(params.get("min_seq_no", 0))
            elif command == "get_sticker_albums":
                return await boxim_message_sender.get_sticker_albums()
            elif command == "get_stickers":
                return await boxim_message_sender.get_stickers(params["album_id"])
            elif command == "search_stickers":
                return await boxim_message_sender.search_stickers(params["name"])
            elif command == "get_custom_stickers":
                return await boxim_message_sender.get_custom_stickers()
            elif command == "get_system_message_content":
                return await boxim_message_sender.get_system_message_content(params["message_id"])
            elif command == "submit_complaint":
                return await boxim_message_sender.submit_complaint(
                    params["target_type"], params["target_id"],
                    params.get("complaint_type", 99), params["content"],
                    params.get("target_name", ""), params.get("images", []))
            elif command == "get_realname_auth_info":
                return await boxim_message_sender.get_realname_auth_info()
            return {}
        except Exception as e:
            logger.error(f"Query command {command} failed: {e}")
            return {"error": str(e)}

    async def _execute_command(self, command: str, params: Dict) -> bool:
        """Execute a command via BoxIM SDK"""
        try:
            if command in ["set_group_ban", "set_group_whole_ban"]:
                return await boxim_message_sender.set_group_muted(
                    params["group_id"], params.get("muted", params.get("enable", False))
                )
            elif command == "set_group_name":
                return await boxim_message_sender.modify_group(
                    params["group_id"], name=params["name"]
                )
            elif command == "modify_group_notice":
                return await boxim_message_sender.modify_group(
                    params["group_id"], notice=params["notice"]
                )
            elif command == "delete_msg":
                msg_id = params["message_id"]
                is_group = params.get("is_group", True)
                return await boxim_message_sender.recall_message(msg_id, is_group=is_group)
            elif command == "create_group":
                return await boxim_message_sender.create_group(
                    params["name"], params.get("member_ids") or []
                )
            elif command == "join_group":
                return await boxim_message_sender.join_group(
                    params["group_id"], params.get("token")
                )
            elif command == "quit_group":
                return await boxim_message_sender.quit_group(params["group_id"])
            elif command == "delete_group":
                return await boxim_message_sender.delete_group(params["group_id"])
            elif command == "invite_to_group":
                return await boxim_message_sender.invite_to_group(
                    params["group_id"], params["user_ids"]
                )
            elif command == "remove_group_members":
                return await boxim_message_sender.remove_group_members(
                    params["group_id"], params["user_ids"]
                )
            elif command == "set_member_mute":
                return await boxim_message_sender.set_group_member_muted(
                    params["group_id"], params["user_ids"], params.get("muted", False)
                )
            elif command == "set_group_dnd":
                return await boxim_message_sender.set_group_dnd(
                    params["group_id"], params.get("value", params.get("dnd", False))
                )
            elif command == "set_group_top":
                return await boxim_message_sender.set_group_top(
                    params["group_id"], params.get("value", params.get("top", False))
                )
            elif command == "set_group_allow_invite":
                return await boxim_message_sender.set_group_allow_invite(
                    params["group_id"], params.get("value", params.get("allow", False))
                )
            elif command == "set_group_allow_share_card":
                return await boxim_message_sender.set_group_allow_share_card(
                    params["group_id"], params.get("value", params.get("allow", False))
                )
            elif command == "add_group_manager":
                return await boxim_message_sender.add_group_manager(
                    params["group_id"], params["user_ids"]
                )
            elif command == "remove_group_manager":
                return await boxim_message_sender.remove_group_manager(
                    params["group_id"], params["user_ids"]
                )
            elif command == "set_group_top_message":
                return await boxim_message_sender.set_group_top_message(
                    params["group_id"], params["message_id"]
                )
            elif command == "remove_group_top_message":
                return await boxim_message_sender.remove_group_top_message(params["group_id"])
            elif command == "hide_group_top_message":
                return await boxim_message_sender.hide_group_top_message(params["group_id"])
            elif command == "add_friend":
                return await boxim_message_sender.add_friend(
                    params["user_id"], params.get("remark")
                )
            elif command == "delete_friend":
                return await boxim_message_sender.delete_friend(params["user_id"])
            elif command == "add_to_blacklist":
                return await boxim_message_sender.add_to_blacklist(params["user_id"])
            elif command == "remove_from_blacklist":
                return await boxim_message_sender.remove_from_blacklist(params["user_id"])
            elif command == "set_friend_dnd":
                return await boxim_message_sender.set_friend_dnd(
                    params["user_id"], params.get("dnd", params.get("value", False))
                )
            elif command == "set_friend_top":
                return await boxim_message_sender.set_friend_top(
                    params["user_id"], params.get("top", params.get("value", False))
                )
            elif command == "update_friend_remark":
                return await boxim_message_sender.update_friend_remark(
                    params["user_id"], params.get("remark", params.get("value", ""))
                )
            elif command == "accept_friend_request":
                return await boxim_message_sender.accept_friend_request(params["request_id"])
            elif command == "reject_friend_request":
                return await boxim_message_sender.reject_friend_request(params["request_id"])
            elif command == "recall_friend_request":
                return await boxim_message_sender.recall_friend_request(params["request_id"])
            elif command == "delete_private_messages":
                return await boxim_message_sender.delete_private_messages(
                    params["chat_id"], params["message_ids"]
                )
            elif command == "delete_group_messages":
                return await boxim_message_sender.delete_group_messages(
                    params["chat_id"], params["message_ids"]
                )
            elif command == "delete_private_chat":
                return await boxim_message_sender.delete_private_chat(params["chat_id"])
            elif command == "delete_group_chat":
                return await boxim_message_sender.delete_group_chat(params["chat_id"])
            elif command == "mark_private_read":
                return await boxim_message_sender.mark_private_read(
                    params["friend_id"], params.get("message_id")
                )
            elif command == "mark_group_read":
                return await boxim_message_sender.mark_group_read(
                    params["group_id"], params.get("message_id")
                )
            elif command == "mark_system_read":
                return await boxim_message_sender.mark_system_read(params["max_seq_no"])
            elif command == "add_custom_sticker":
                return await boxim_message_sender.add_custom_sticker(
                    params["name"], params["image_url"], params.get("thumb_url", params["image_url"]),
                    params.get("width", 100), params.get("height", 100)
                )
            elif command == "delete_custom_sticker":
                return await boxim_message_sender.delete_custom_sticker(params["sticker_id"])
            elif command == "top_custom_sticker":
                return await boxim_message_sender.top_custom_sticker(params["sticker_id"])
            elif command == "update_profile":
                return await boxim_message_sender.update_profile(**params)
            elif command == "submit_realname_auth":
                return await boxim_message_sender.submit_realname_auth(
                    params["real_name"], params["id_card"]
                )
            else:
                logger.warning(f"Unknown command: {command}")
                return False
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False

    async def _send_command_response(
        self,
        platform: str,
        command_name: str,
        success: bool,
        data: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> None:
        """Send command response back to MaiBot"""
        response_data = {
            "command_name": command_name,
            "success": success,
            "timestamp": time.time()
        }

        if data is not None:
            response_data["data"] = data
        if error:
            response_data["error"] = error

        try:
            await message_send_instance.send_custom_message(
                custom_message=response_data,
                platform=platform,
                message_type="command_response"
            )
            logger.debug(f"Command response sent: {command_name}, success={success}")
        except Exception as e:
            logger.error(f"Failed to send command response: {e}")

    async def send_normal_message(self, raw_message_base: MessageBase) -> None:
        """Handle normal message sending"""
        logger.info("Processing normal message")
        message_info: BaseMessageInfo = raw_message_base.message_info
        message_segment: Seg = raw_message_base.message_segment
        group_info, user_info = self._extract_target_info(message_info)

        processed_message = []
        try:
            processed_message = SendMessageHandleClass.process_seg_recursive(message_segment)
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return

        if not processed_message:
            logger.critical("Message parsing not supported!")
            return

        # Determine target and send
        if group_info and user_info:
            logger.debug("Sending group message")
            await self._send_group_messages(group_info.group_id, processed_message, raw_message_base)
        elif user_info:
            logger.debug("Sending private message")
            await self._send_private_messages(user_info.user_id, processed_message, raw_message_base)
        else:
            logger.error("Unrecognizable message type")
            return

    async def _send_private_messages(self, user_id: int, segments: list, original_message_base: MessageBase = None) -> bool:
        """Send a list of segments as private messages"""
        # Extract quote_message_id from reply segment
        quote_message_id = None
        for seg in segments:
            if seg.get("type") == "reply":
                reply_data = seg.get("data", {})
                if isinstance(reply_data, dict):
                    quote_message_id = reply_data.get("id")
                elif isinstance(reply_data, str):
                    quote_message_id = reply_data
                if quote_message_id:
                    quote_message_id = int(quote_message_id)
                break

        for seg in segments:
            seg_type = seg.get("type")
            seg_data = seg.get("data", {})

            if seg_type == "text":
                text = seg_data.get("text", "")
                sent_msg_id = await boxim_message_sender.send_text(user_id, text, quote_message_id)
                if sent_msg_id and original_message_base:
                    await self._send_message_id_echo(original_message_base, sent_msg_id)
                quote_message_id = None  # Only quote once
            elif seg_type == "reply":
                pass  # Already handled
            elif seg_type == "image":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "image", user_id, is_group=False)
                if not result:
                    logger.warning(f"私聊图片发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "emoji":
                # MaiBot emoji 作为图片发送
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "image", user_id, is_group=False)
                if not result:
                    logger.warning(f"私聊 emoji 发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "voice":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "voice", user_id, is_group=False)
                if not result:
                    logger.warning(f"私聊语音发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "video":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "video", user_id, is_group=False)
                if not result:
                    logger.warning(f"私聊视频发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "file":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "file", user_id, is_group=False)
                if not result:
                    logger.warning(f"私聊文件发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "face":
                # BoxIM stickers map to face
                face_id = seg_data.get("id")
                if face_id is not None:
                    try:
                        await boxim_message_sender.send_sticker(user_id, int(face_id))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid face_id '{face_id}': {e}")
            else:
                logger.warning(f"Unsupported segment type for private message: {seg_type}")
        return True

    async def _send_group_messages(self, group_id: int, segments: list, original_message_base: MessageBase = None) -> bool:
        """Send a list of segments as group messages"""
        # Collect at users from all at segments
        at_users = []
        for seg in segments:
            if seg.get("type") == "at":
                at_data = seg.get("data", {})
                uid = at_data.get("user_id")
                if uid is not None:
                    at_users.append(int(uid))

        # Extract quote_message_id from reply segment
        quote_message_id = None
        for seg in segments:
            if seg.get("type") == "reply":
                reply_data = seg.get("data", {})
                if isinstance(reply_data, dict):
                    quote_message_id = reply_data.get("id")
                elif isinstance(reply_data, str):
                    quote_message_id = reply_data
                if quote_message_id:
                    quote_message_id = int(quote_message_id)
                break

        for seg in segments:
            seg_type = seg.get("type")
            seg_data = seg.get("data", {})

            if seg_type == "text":
                text = seg_data.get("text", "")
                sent_msg_id = await boxim_message_sender.send_group_text(group_id, text, at_users if at_users else None, quote_message_id)
                if sent_msg_id and original_message_base:
                    await self._send_message_id_echo(original_message_base, sent_msg_id)
                quote_message_id = None  # Only quote once
            elif seg_type == "reply":
                pass  # Already handled
            elif seg_type == "at":
                pass  # Already collected above
            elif seg_type == "image":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "image", group_id, is_group=True)
                if not result:
                    logger.warning(f"群聊图片发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "emoji":
                # MaiBot emoji 作为图片发送
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "image", group_id, is_group=True)
                if not result:
                    logger.warning(f"群聊 emoji 发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "voice":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "voice", group_id, is_group=True)
                if not result:
                    logger.warning(f"群聊语音发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "video":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "video", group_id, is_group=True)
                if not result:
                    logger.warning(f"群聊视频发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "file":
                file_path = seg_data.get("file", "")
                result = await self._handle_file_send(file_path, "file", group_id, is_group=True)
                if not result:
                    logger.warning(f"群聊文件发送失败，继续处理后续消息段: {file_path[:50]}")
            elif seg_type == "face":
                face_id = seg_data.get("id")
                if face_id is not None:
                    try:
                        await boxim_message_sender.send_group_sticker(group_id, int(face_id))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid face_id '{face_id}': {e}")
            else:
                logger.warning(f"Unsupported segment type for group message: {seg_type}")
        return True

    async def _handle_file_send(self, file_path: str, file_type: str, target_id: int, is_group: bool) -> bool:
        """Handle file sending - supports local path, URL, or base64"""
        if not file_path:
            logger.error("File path is empty")
            return False

        try:
            # Handle base64:// prefixed data
            if file_path.startswith("base64://"):
                return await self._send_base64_file(file_path[9:], file_type, target_id, is_group)
            elif file_path.startswith("file://"):
                local_path = file_path[7:]
                return await self._send_local_file(local_path, file_type, target_id, is_group)
            elif file_path.startswith(("http://", "https://")):
                return await self._send_url_file(file_path, file_type, target_id, is_group)
            else:
                # Assume local file path
                return await self._send_local_file(file_path, file_type, target_id, is_group)
        except Exception as e:
            logger.error(f"File sending failed for {file_type}: {e}")
            return False

    async def _send_base64_file(self, b64_data: str, file_type: str, target_id: int, is_group: bool) -> bool:
        """Send file from base64 data"""
        try:
            file_bytes = base64.b64decode(b64_data)
            ext = self._get_file_extension(file_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                return await self._send_local_file(tmp_path, file_type, target_id, is_group)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Base64 file decode failed: {e}")
            return False

    async def _send_local_file(self, file_path: str, file_type: str, target_id: int, is_group: bool) -> bool:
        """Send local file"""
        if not os.path.exists(file_path):
            logger.error(f"Local file not found: {file_path}")
            return False

        try:
            if is_group:
                if file_type == "image":
                    return await boxim_message_sender.send_group_image(target_id, file_path)
                elif file_type == "voice":
                    return await boxim_message_sender.send_group_voice(target_id, file_path)
                elif file_type == "video":
                    return await boxim_message_sender.send_group_video(target_id, file_path)
                elif file_type == "file":
                    return await boxim_message_sender.send_group_file(target_id, file_path)
            else:
                if file_type == "image":
                    return await boxim_message_sender.send_image(target_id, file_path)
                elif file_type == "voice":
                    return await boxim_message_sender.send_voice(target_id, file_path)
                elif file_type == "video":
                    return await boxim_message_sender.send_video(target_id, file_path)
                elif file_type == "file":
                    return await boxim_message_sender.send_file(target_id, file_path)
        except Exception as e:
            logger.error(f"Local file send failed: {e}")
            return False
        return False

    async def _send_url_file(self, url: str, file_type: str, target_id: int, is_group: bool) -> bool:
        """For URL-based files, download first then send"""
        from src.utils import download_url

        try:
            file_bytes = await download_url(url)
            if not file_bytes:
                return False

            ext = self._get_file_extension(file_type)
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                return await self._send_local_file(tmp_path, file_type, target_id, is_group)
            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"URL file download failed: {e}")
            return False

    @staticmethod
    def _get_file_extension(file_type: str) -> str:
        extensions = {
            "image": ".png",
            "voice": ".ogg",
            "video": ".mp4",
            "file": "",
        }
        return extensions.get(file_type, "")


send_handler = SendHandler()
