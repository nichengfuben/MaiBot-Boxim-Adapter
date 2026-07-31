"""Action command handlers (module-level map keeps functions short)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from src.runtime.logger import logger
from src.send_handler.im_sending import boxim_message_sender

Handler = Callable[[Dict[str, Any]], Awaitable[bool]]


async def _ban(params: Dict[str, Any]) -> bool:
    return await boxim_message_sender.set_group_muted(
        params["group_id"], params.get("muted", params.get("enable", False))
    )


async def _set_name(params: Dict[str, Any]) -> bool:
    return await boxim_message_sender.modify_group(params["group_id"], name=params["name"])


async def _set_notice(params: Dict[str, Any]) -> bool:
    return await boxim_message_sender.modify_group(
        params["group_id"], notice=params["notice"]
    )


async def _delete_msg(params: Dict[str, Any]) -> bool:
    return await boxim_message_sender.recall_message(
        params["message_id"], is_group=params.get("is_group", True)
    )


async def _create_group(params: Dict[str, Any]) -> bool:
    return await boxim_message_sender.create_group(
        params["name"], params.get("member_ids") or []
    )


ACTION_HANDLERS: Dict[str, Handler] = {
    "set_group_ban": _ban,
    "set_group_whole_ban": _ban,
    "set_group_name": _set_name,
    "modify_group_notice": _set_notice,
    "delete_msg": _delete_msg,
    "create_group": _create_group,
    "join_group": lambda p: boxim_message_sender.join_group(p["group_id"], p.get("token")),
    "quit_group": lambda p: boxim_message_sender.quit_group(p["group_id"]),
    "delete_group": lambda p: boxim_message_sender.delete_group(p["group_id"]),
    "invite_to_group": lambda p: boxim_message_sender.invite_to_group(
        p["group_id"], p["user_ids"]
    ),
    "remove_group_members": lambda p: boxim_message_sender.remove_group_members(
        p["group_id"], p["user_ids"]
    ),
    "set_member_mute": lambda p: boxim_message_sender.set_group_member_muted(
        p["group_id"], p["user_ids"], p.get("muted", False)
    ),
    "set_group_dnd": lambda p: boxim_message_sender.set_group_dnd(
        p["group_id"], p.get("value", p.get("dnd", False))
    ),
    "set_group_top": lambda p: boxim_message_sender.set_group_top(
        p["group_id"], p.get("value", p.get("top", False))
    ),
    "set_group_allow_invite": lambda p: boxim_message_sender.set_group_allow_invite(
        p["group_id"], p.get("value", p.get("allow", False))
    ),
    "set_group_allow_share_card": lambda p: boxim_message_sender.set_group_allow_share_card(
        p["group_id"], p.get("value", p.get("allow", False))
    ),
    "add_group_manager": lambda p: boxim_message_sender.add_group_manager(
        p["group_id"], p["user_ids"]
    ),
    "remove_group_manager": lambda p: boxim_message_sender.remove_group_manager(
        p["group_id"], p["user_ids"]
    ),
    "set_group_top_message": lambda p: boxim_message_sender.set_group_top_message(
        p["group_id"], p["message_id"]
    ),
    "remove_group_top_message": lambda p: boxim_message_sender.remove_group_top_message(
        p["group_id"]
    ),
    "hide_group_top_message": lambda p: boxim_message_sender.hide_group_top_message(
        p["group_id"]
    ),
    "add_friend": lambda p: boxim_message_sender.add_friend(p["user_id"], p.get("remark")),
    "delete_friend": lambda p: boxim_message_sender.delete_friend(p["user_id"]),
    "add_to_blacklist": lambda p: boxim_message_sender.add_to_blacklist(p["user_id"]),
    "remove_from_blacklist": lambda p: boxim_message_sender.remove_from_blacklist(
        p["user_id"]
    ),
    "set_friend_dnd": lambda p: boxim_message_sender.set_friend_dnd(
        p["user_id"], p.get("dnd", p.get("value", False))
    ),
    "set_friend_top": lambda p: boxim_message_sender.set_friend_top(
        p["user_id"], p.get("top", p.get("value", False))
    ),
    "update_friend_remark": lambda p: boxim_message_sender.update_friend_remark(
        p["user_id"], p.get("remark", p.get("value", ""))
    ),
    "accept_friend_request": lambda p: boxim_message_sender.accept_friend_request(
        p["request_id"]
    ),
    "reject_friend_request": lambda p: boxim_message_sender.reject_friend_request(
        p["request_id"]
    ),
    "recall_friend_request": lambda p: boxim_message_sender.recall_friend_request(
        p["request_id"]
    ),
    "delete_private_messages": lambda p: boxim_message_sender.delete_private_messages(
        p["chat_id"], p["message_ids"]
    ),
    "delete_group_messages": lambda p: boxim_message_sender.delete_group_messages(
        p["chat_id"], p["message_ids"]
    ),
    "delete_private_chat": lambda p: boxim_message_sender.delete_private_chat(p["chat_id"]),
    "delete_group_chat": lambda p: boxim_message_sender.delete_group_chat(p["chat_id"]),
    "mark_private_read": lambda p: boxim_message_sender.mark_private_read(
        p["friend_id"], p.get("message_id")
    ),
    "mark_group_read": lambda p: boxim_message_sender.mark_group_read(
        p["group_id"], p.get("message_id")
    ),
    "mark_system_read": lambda p: boxim_message_sender.mark_system_read(p["max_seq_no"]),
    "add_custom_sticker": lambda p: boxim_message_sender.add_custom_sticker(
        p["name"],
        p["image_url"],
        p.get("thumb_url", p["image_url"]),
        p.get("width", 100),
        p.get("height", 100),
    ),
    "delete_custom_sticker": lambda p: boxim_message_sender.delete_custom_sticker(
        p["sticker_id"]
    ),
    "top_custom_sticker": lambda p: boxim_message_sender.top_custom_sticker(p["sticker_id"]),
    "update_profile": lambda p: boxim_message_sender.update_profile(**p),
    "submit_realname_auth": lambda p: boxim_message_sender.submit_realname_auth(
        p["real_name"], p["id_card"]
    ),
}


class ActionMixin:
    async def _execute_command(self, command: str, params: Dict) -> bool:
        """Execute a command via BoxIM SDK."""
        handler = ACTION_HANDLERS.get(command)
        if handler is None:
            logger.warning(f"Unknown command: {command}")
            return False
        try:
            return await handler(params)
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return False
