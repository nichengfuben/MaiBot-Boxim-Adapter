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
from src.runtime.logger import logger
from .cmd_api import SendCommandHandleClass
from .msg_format import SendMessageHandleClass
from .im_sending import boxim_message_sender
from src.recv_handler.message_sending import message_send_instance
from src.send_handler.send_ops import QueryMixin, ActionMixin, OutboundMixin



class SendHandler(QueryMixin, ActionMixin, OutboundMixin):
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
        message_info = raw_message_base.message_info
        group_info, _ = self._extract_target_info(message_info)
        seg_data: Dict[str, Any] = raw_message_base.message_segment.data
        command_name = seg_data.get("name", "UNKNOWN")
        try:
            command, params_dict = SendCommandHandleClass.handle_command(seg_data, group_info)
        except Exception as e:
            logger.error(f"Error processing command: {str(e)}")
            await self._reply_cmd(message_info.platform, command_name, False, error=str(e))
            return
        if not command or not params_dict:
            logger.error("Command or params missing")
            await self._reply_cmd(
                message_info.platform, command_name, False, error="Command or params missing"
            )
            return
        await self._run_parsed_command(message_info.platform, command_name, command, params_dict)

    async def _reply_cmd(self, platform, command_name, success, data=None, error=None):
        await self._send_command_response(
            platform=platform, command_name=command_name, success=success, data=data, error=error
        )

    async def _run_parsed_command(self, platform, command_name, command, params_dict):
        from src.send_handler.send_ops.queries import QUERY_HANDLERS

        if command in QUERY_HANDLERS:
            result = await self._execute_query_command(command, params_dict)
            ok = not (result and "error" in result)
            await self._reply_cmd(
                platform,
                command_name,
                ok,
                data=result if ok else None,
                error=(result or {}).get("error") if not ok else None,
            )
            return
        success = await self._execute_command(command, params_dict)
        await self._reply_cmd(
            platform,
            command_name,
            success,
            error=None if success else "BoxIM SDK execution failed",
        )
        logger.info(f"Command {command_name} executed successfully") if success else logger.warning(
            f"Command {command_name} failed"
        )
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


send_handler = SendHandler()
