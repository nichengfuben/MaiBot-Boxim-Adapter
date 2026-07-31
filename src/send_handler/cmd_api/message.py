from typing import Any, Dict

from src.commands import CommandType
from src.send_handler.cmd_api.registry import register_command


@register_command(CommandType.GET_GROUP_MEMBER_INFO, require_group=False)
def handle_get_group_member_info_command(args: Dict[str, Any], group_info) -> tuple:
    """映射到 get_user_info"""
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})


@register_command(CommandType.GET_MSG, require_group=False)
def handle_get_msg_command(args: Dict[str, Any], group_info) -> tuple:
    """获取消息 - BoxIM 暂无直接获取单条消息 API"""
    return (CommandType.GET_MSG.value, {"error": "BoxIM 暂不支持"})


@register_command(CommandType.GET_FORWARD_MSG, require_group=False)
def handle_get_forward_msg_command(args: Dict[str, Any], group_info) -> tuple:
    """获取合并转发 - BoxIM 暂无此 API"""
    return (CommandType.GET_FORWARD_MSG.value, {"error": "BoxIM 暂不支持"})

# ============ 好友设置命令 ============


@register_command(CommandType.SET_FRIEND_DND, require_group=False)
def handle_set_friend_dnd_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    value = args.get("value", args.get("dnd", False))
    if not isinstance(value, bool):
        value = bool(value)
    return (CommandType.SET_FRIEND_DND.value, {"user_id": int(user_id), "dnd": value})


@register_command(CommandType.SET_FRIEND_TOP, require_group=False)
def handle_set_friend_top_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    value = args.get("value", args.get("top", False))
    if not isinstance(value, bool):
        value = bool(value)
    return (CommandType.SET_FRIEND_TOP.value, {"user_id": int(user_id), "top": value})


@register_command(CommandType.UPDATE_FRIEND_REMARK, require_group=False)
def handle_update_friend_remark_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    remark = args.get("remark", args.get("value", ""))
    if not user_id:
        raise ValueError("Missing: user_id")
    if not remark:
        raise ValueError("Missing: remark")
    return (CommandType.UPDATE_FRIEND_REMARK.value, {"user_id": int(user_id), "remark": str(remark)})

# ============ 好友信息查询 ============


@register_command(CommandType.GET_FRIEND_INFO, require_group=False)
def handle_get_friend_info_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.GET_FRIEND_INFO.value, {"user_id": int(user_id)})

# ============ 好友请求 ============


@register_command(CommandType.GET_FRIEND_REQUESTS, require_group=False)
def handle_get_friend_requests_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_FRIEND_REQUESTS.value, {})


@register_command(CommandType.ACCEPT_FRIEND_REQUEST, require_group=False)
def handle_accept_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
    request_id = args.get("request_id")
    if not request_id:
        raise ValueError("Missing: request_id")
    return (CommandType.ACCEPT_FRIEND_REQUEST.value, {"request_id": int(request_id)})


@register_command(CommandType.REJECT_FRIEND_REQUEST, require_group=False)
def handle_reject_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
    request_id = args.get("request_id")
    if not request_id:
        raise ValueError("Missing: request_id")
    return (CommandType.REJECT_FRIEND_REQUEST.value, {"request_id": int(request_id)})


@register_command(CommandType.RECALL_FRIEND_REQUEST, require_group=False)
def handle_recall_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
    request_id = args.get("request_id")
    if not request_id:
        raise ValueError("Missing: request_id")
    return (CommandType.RECALL_FRIEND_REQUEST.value, {"request_id": int(request_id)})

# ============ 消息操作 ============


@register_command(CommandType.DELETE_PRIVATE_MESSAGES, require_group=False)
def handle_delete_private_messages_command(args: Dict[str, Any], group_info) -> tuple:
    chat_id = args.get("chat_id")
    message_ids = args.get("message_ids", [])
    if not chat_id:
        raise ValueError("Missing: chat_id")
    if not message_ids:
        raise ValueError("Missing: message_ids")
    return (CommandType.DELETE_PRIVATE_MESSAGES.value, {"chat_id": int(chat_id), "message_ids": [int(mid) for mid in message_ids]})


@register_command(CommandType.DELETE_GROUP_MESSAGES, require_group=False)
def handle_delete_group_messages_command(args: Dict[str, Any], group_info) -> tuple:
    chat_id = args.get("chat_id")
    message_ids = args.get("message_ids", [])
    if not chat_id:
        raise ValueError("Missing: chat_id")
    if not message_ids:
        raise ValueError("Missing: message_ids")
    return (CommandType.DELETE_GROUP_MESSAGES.value, {"chat_id": int(chat_id), "message_ids": [int(mid) for mid in message_ids]})


@register_command(CommandType.DELETE_PRIVATE_CHAT, require_group=False)
def handle_delete_private_chat_command(args: Dict[str, Any], group_info) -> tuple:
    chat_id = args.get("chat_id")
    if not chat_id:
        raise ValueError("Missing: chat_id")
    return (CommandType.DELETE_PRIVATE_CHAT.value, {"chat_id": int(chat_id)})


@register_command(CommandType.DELETE_GROUP_CHAT, require_group=False)
def handle_delete_group_chat_command(args: Dict[str, Any], group_info) -> tuple:
    chat_id = args.get("chat_id")
    if not chat_id:
        raise ValueError("Missing: chat_id")
    return (CommandType.DELETE_GROUP_CHAT.value, {"chat_id": int(chat_id)})


@register_command(CommandType.GET_PRIVATE_MESSAGE_HISTORY, require_group=False)
def handle_get_private_message_history_command(args: Dict[str, Any], group_info) -> tuple:
    friend_id = args.get("friend_id")
    if not friend_id:
        raise ValueError("Missing: friend_id")
    result = {"friend_id": int(friend_id)}
    if args.get("min_seq_no") is not None:
        result["min_seq_no"] = int(args["min_seq_no"])
    if args.get("max_seq_no") is not None:
        result["max_seq_no"] = int(args["max_seq_no"])
    return (CommandType.GET_PRIVATE_MESSAGE_HISTORY.value, result)


@register_command(CommandType.GET_GROUP_MESSAGE_HISTORY, require_group=False)
def handle_get_group_message_history_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    result = {"group_id": int(group_id)}
    if args.get("min_seq_no") is not None:
        result["min_seq_no"] = int(args["min_seq_no"])
    if args.get("max_seq_no") is not None:
        result["max_seq_no"] = int(args["max_seq_no"])
    return (CommandType.GET_GROUP_MESSAGE_HISTORY.value, result)


@register_command(CommandType.MARK_PRIVATE_READ, require_group=False)
def handle_mark_private_read_command(args: Dict[str, Any], group_info) -> tuple:
    friend_id = args.get("friend_id")
    if not friend_id:
        raise ValueError("Missing: friend_id")
    result = {"friend_id": int(friend_id)}
    if args.get("message_id") is not None:
        result["message_id"] = int(args["message_id"])
    return (CommandType.MARK_PRIVATE_READ.value, result)


@register_command(CommandType.MARK_GROUP_READ, require_group=False)
def handle_mark_group_read_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    result = {"group_id": int(group_id)}
    if args.get("message_id") is not None:
        result["message_id"] = int(args["message_id"])
    return (CommandType.MARK_GROUP_READ.value, result)


@register_command(CommandType.GET_GROUP_MESSAGE_READERS, require_group=False)
def handle_get_group_message_readers_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    message_id = args.get("message_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    if not message_id:
        raise ValueError("Missing: message_id")
    return (CommandType.GET_GROUP_MESSAGE_READERS.value, {"group_id": int(group_id), "message_id": int(message_id)})

# ============ 离线消息 ============

