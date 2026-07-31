from typing import Any, Dict

from src.commands import CommandType
from src.send_handler.cmd_api.registry import register_command


@register_command(CommandType.REMOVE_GROUP_TOP_MESSAGE, require_group=False)
def handle_remove_group_top_message_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.REMOVE_GROUP_TOP_MESSAGE.value,
        {"group_id": int(group_id)},
    )


@register_command(CommandType.HIDE_GROUP_TOP_MESSAGE, require_group=False)
def handle_hide_group_top_message_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.HIDE_GROUP_TOP_MESSAGE.value,
        {"group_id": int(group_id)},
    )


@register_command(CommandType.GET_GROUP_MEMBER_LIST, require_group=False)
def handle_get_group_member_list_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.GET_GROUP_MEMBER_LIST.value,
        {"group_id": int(group_id)},
    )

# ============ 新增命令 ============


@register_command(CommandType.GET_ME, require_group=False)
def handle_get_me_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_ME.value, {})


@register_command(CommandType.GET_USER_INFO, require_group=False)
def handle_get_user_info_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})


@register_command(CommandType.SEARCH_USERS, require_group=False)
def handle_search_users_command(args: Dict[str, Any], group_info) -> tuple:
    keyword = args.get("keyword", "")
    if not keyword:
        raise ValueError("Missing: keyword")
    return (CommandType.SEARCH_USERS.value, {"keyword": str(keyword)})


@register_command(CommandType.GET_GROUP_ONLINE_MEMBERS, require_group=False)
def handle_get_group_online_members_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.GET_GROUP_ONLINE_MEMBERS.value,
        {"group_id": int(group_id)},
    )


@register_command(CommandType.ADD_FRIEND, require_group=False)
def handle_add_friend_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    remark = args.get("remark")
    return (
        CommandType.ADD_FRIEND.value,
        {"user_id": int(user_id), "remark": str(remark) if remark else None},
    )


@register_command(CommandType.DELETE_FRIEND, require_group=False)
def handle_delete_friend_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.DELETE_FRIEND.value, {"user_id": int(user_id)})


@register_command(CommandType.ADD_TO_BLACKLIST, require_group=False)
def handle_add_to_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.ADD_TO_BLACKLIST.value, {"user_id": int(user_id)})


@register_command(CommandType.REMOVE_FROM_BLACKLIST, require_group=False)
def handle_remove_from_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.REMOVE_FROM_BLACKLIST.value, {"user_id": int(user_id)})


@register_command(CommandType.GET_BLACKLIST, require_group=False)
def handle_get_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_BLACKLIST.value, {})


@register_command(CommandType.JOIN_GROUP, require_group=False)
def handle_join_group_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    token = args.get("token")
    return (
        CommandType.JOIN_GROUP.value,
        {"group_id": int(group_id), "token": str(token) if token else None},
    )


@register_command(CommandType.SET_MSG_EMOJI_LIKE, require_group=False)
def handle_set_msg_emoji_like_command(args: Dict[str, Any], group_info) -> tuple:
    """BoxIM 不支持贴表情，标记为不支持"""
    return (CommandType.SET_MSG_EMOJI_LIKE.value, {"error": "BoxIM 不支持此功能"})


@register_command(CommandType.GET_STRANGER_INFO, require_group=False)
def handle_get_stranger_info_command(args: Dict[str, Any], group_info) -> tuple:
    """映射到 get_user_info"""
    user_id = args.get("user_id")
    if not user_id:
        raise ValueError("Missing: user_id")
    return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})


@register_command(CommandType.GET_GROUP_DETAIL_INFO, require_group=False)
def handle_get_group_detail_info_command(args: Dict[str, Any], group_info) -> tuple:
    """映射到 get_group_info"""
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (CommandType.GET_GROUP_INFO.value, {"group_id": int(group_id)})

