from typing import Any, Dict

from src.commands import CommandType
from src.send_handler.cmd_api.registry import register_command


@register_command(CommandType.GROUP_BAN, require_group=True)
def handle_ban_command(args: Dict[str, Any], group_info) -> tuple:
    """Handle ban command - BoxIM only supports group-wide mute"""
    duration: int = int(args["duration"])
    group_id: int = int(group_info.group_id)
    if duration < 0:
        raise ValueError("Ban duration must be >= 0")
    if duration > 2592000:
        raise ValueError("Ban duration cannot exceed 30 days")
    # BoxIM only has group-wide mute, no per-user mute
    # We map individual ban to group-wide mute if duration > 0
    return (
        CommandType.GROUP_BAN.value,
        {
            "group_id": group_id,
            "muted": duration > 0,
        },
    )


@register_command(CommandType.GROUP_WHOLE_BAN, require_group=True)
def handle_whole_ban_command(args: Dict[str, Any], group_info) -> tuple:
    """Handle group-wide ban command"""
    enable = args["enable"]
    assert isinstance(enable, bool), "enable must be boolean"
    group_id: int = int(group_info.group_id)
    if group_id <= 0:
        raise ValueError("Invalid group ID")
    return (
        CommandType.GROUP_WHOLE_BAN.value,
        {
            "group_id": group_id,
            "muted": enable,
        },
    )


@register_command(CommandType.GROUP_KICK, require_group=False)
def handle_kick_command(args: Dict[str, Any], group_info) -> tuple:
    """Kick group member - mapped to remove_group_members"""
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_id = args.get("user_id")
    if not group_id:
        raise ValueError("Kick command missing: group_id")
    if not user_id:
        raise ValueError("Kick command missing: user_id")
    return (
        CommandType.REMOVE_GROUP_MEMBERS.value,
        {
            "group_id": int(group_id),
            "user_ids": [int(user_id)],
        },
    )


@register_command(CommandType.GROUP_KICK_MEMBERS, require_group=False)
def handle_kick_members_command(args: Dict[str, Any], group_info) -> tuple:
    """Batch kick - mapped to remove_group_members"""
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_id = args.get("user_id")
    if not group_id:
        raise ValueError("Batch kick missing: group_id")
    if not user_id:
        raise ValueError("Batch kick missing: user_id")
    if not isinstance(user_id, list):
        raise ValueError("user_id must be a list")
    return (
        CommandType.REMOVE_GROUP_MEMBERS.value,
        {
            "group_id": int(group_id),
            "user_ids": [int(uid) for uid in user_id],
        },
    )


@register_command(CommandType.SET_GROUP_NAME, require_group=False)
def handle_set_group_name_command(args: Dict[str, Any], group_info) -> tuple:
    """Set group name"""
    if not args:
        raise ValueError("Set group name missing args")

    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)

    group_name = args.get("group_name")

    if not group_id:
        raise ValueError("Set group name missing: group_id")
    if not group_name:
        raise ValueError("Set group name missing: group_name")

    return (
        CommandType.SET_GROUP_NAME.value,
        {
            "group_id": int(group_id),
            "name": str(group_name),
        },
    )


@register_command(CommandType.DELETE_MSG, require_group=False)
def delete_msg_command(args: Dict[str, Any], group_info) -> tuple:
    """Recall message"""
    try:
        message_id = int(args["message_id"])
        if message_id <= 0:
            raise ValueError("Invalid message ID")
    except KeyError:
        raise ValueError("Missing required param: message_id") from None
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid message ID: {args['message_id']} - {str(e)}") from None

    is_group = args.get("is_group", True)
    return (CommandType.DELETE_MSG.value, {"message_id": message_id, "is_group": is_group})

# ============ Query Commands ============


@register_command(CommandType.GET_LOGIN_INFO, require_group=False)
def handle_get_login_info_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_LOGIN_INFO.value, {})


@register_command(CommandType.GET_FRIEND_LIST, require_group=False)
def handle_get_friend_list_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_FRIEND_LIST.value, {})


@register_command(CommandType.GET_GROUP_INFO, require_group=False)
def handle_get_group_info_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id") if args else None
    if not group_id and group_info:
        group_id = int(group_info.group_id)

    if not group_id:
        raise ValueError("Get group info missing: group_id")

    return (
        CommandType.GET_GROUP_INFO.value,
        {"group_id": int(group_id)},
    )


@register_command(CommandType.GET_GROUP_LIST, require_group=False)
def handle_get_group_list_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_GROUP_LIST.value, {})

# ============ 群组管理命令 ============


@register_command(CommandType.CREATE_GROUP, require_group=False)
def handle_create_group_command(args: Dict[str, Any], group_info) -> tuple:
    name = args.get("name")
    if not name:
        raise ValueError("Missing: name")
    member_ids = args.get("member_ids", [])
    if not isinstance(member_ids, list):
        raise ValueError("member_ids must be a list")
    return (
        CommandType.CREATE_GROUP.value,
        {"name": str(name), "member_ids": [int(uid) for uid in member_ids]},
    )


@register_command(CommandType.MODIFY_GROUP_NOTICE, require_group=False)
def handle_modify_group_notice_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    notice = args.get("notice")
    if not group_id:
        raise ValueError("Missing: group_id")
    if notice is None:
        raise ValueError("Missing: notice")
    return (
        CommandType.MODIFY_GROUP_NOTICE.value,
        {"group_id": int(group_id), "notice": str(notice)},
    )

