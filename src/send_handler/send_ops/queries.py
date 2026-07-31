"""Query command handlers (module-level map keeps functions short)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from src.runtime.logger import logger
from src.send_handler.im_sending import boxim_message_sender

Handler = Callable[[Dict[str, Any]], Awaitable[Any]]

QUERY_HANDLERS: Dict[str, Handler] = {
    "get_login_info": lambda p: boxim_message_sender.get_me(),
    "get_me": lambda p: boxim_message_sender.get_me(),
    "get_group_info": lambda p: boxim_message_sender.get_group_info(p["group_id"]),
    "get_group_list": lambda p: boxim_message_sender.get_groups(),
    "get_group_member_list": lambda p: boxim_message_sender.get_group_members(p["group_id"]),
    "get_user_info": lambda p: boxim_message_sender.get_user_info(p["user_id"]),
    "search_users": lambda p: boxim_message_sender.search_users(p["keyword"]),
    "get_friend_list": lambda p: boxim_message_sender.get_friend_list(),
    "get_friend_info": lambda p: boxim_message_sender.get_friend_info(p["user_id"]),
    "get_friend_requests": lambda p: boxim_message_sender.get_friend_requests(),
    "get_blacklist": lambda p: boxim_message_sender.get_blacklist(),
    "get_group_online_members": lambda p: boxim_message_sender.get_group_online_members(
        p["group_id"]
    ),
    "get_group_message_readers": lambda p: boxim_message_sender.get_group_message_readers(
        p["group_id"], p["message_id"]
    ),
    "get_private_message_history": lambda p: boxim_message_sender.get_private_message_history(
        p["friend_id"], p.get("min_seq_no"), p.get("max_seq_no")
    ),
    "get_group_message_history": lambda p: boxim_message_sender.get_group_message_history(
        p["group_id"], p.get("min_seq_no"), p.get("max_seq_no")
    ),
    "load_private_offline_message": lambda p: boxim_message_sender.load_private_offline_message(
        p.get("min_id", 0)
    ),
    "load_group_offline_message": lambda p: boxim_message_sender.load_group_offline_message(
        p.get("min_id", 0)
    ),
    "load_system_offline_message": lambda p: boxim_message_sender.load_system_offline_message(
        p.get("min_seq_no", 0)
    ),
    "get_sticker_albums": lambda p: boxim_message_sender.get_sticker_albums(),
    "get_stickers": lambda p: boxim_message_sender.get_stickers(p["album_id"]),
    "search_stickers": lambda p: boxim_message_sender.search_stickers(p["name"]),
    "get_custom_stickers": lambda p: boxim_message_sender.get_custom_stickers(),
    "get_system_message_content": lambda p: boxim_message_sender.get_system_message_content(
        p["message_id"]
    ),
    "submit_complaint": lambda p: boxim_message_sender.submit_complaint(
        p["target_type"],
        p["target_id"],
        p.get("complaint_type", 99),
        p["content"],
        p.get("target_name", ""),
        p.get("images", []),
    ),
    "get_realname_auth_info": lambda p: boxim_message_sender.get_realname_auth_info(),
}


class QueryMixin:
    async def _execute_query_command(self, command: str, params: Dict) -> Dict:
        """Execute a query command that returns data."""
        handler = QUERY_HANDLERS.get(command)
        if handler is None:
            return {}
        try:
            return await handler(params)
        except Exception as e:
            logger.error(f"Query command {command} failed: {e}")
            return {"error": str(e)}
