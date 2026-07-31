from typing import Any, Dict

from src.commands import CommandType
from src.send_handler.cmd_api.registry import register_command


@register_command(CommandType.QUIT_GROUP, require_group=False)
def handle_quit_group_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (CommandType.QUIT_GROUP.value, {"group_id": int(group_id)})


@register_command(CommandType.DELETE_GROUP, require_group=False)
def handle_delete_group_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    return (CommandType.DELETE_GROUP.value, {"group_id": int(group_id)})


@register_command(CommandType.INVITE_TO_GROUP, require_group=False)
def handle_invite_to_group_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_ids = args.get("user_ids", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    if not group_id:
        raise ValueError("Missing: group_id")
    if not user_ids:
        raise ValueError("Missing: user_ids")
    return (
        CommandType.INVITE_TO_GROUP.value,
        {"group_id": int(group_id), "user_ids": [int(uid) for uid in user_ids]},
    )


@register_command(CommandType.REMOVE_GROUP_MEMBERS, require_group=False)
def handle_remove_group_members_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_ids = args.get("user_ids", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    if not group_id:
        raise ValueError("Missing: group_id")
    if not user_ids:
        raise ValueError("Missing: user_ids")
    return (
        CommandType.REMOVE_GROUP_MEMBERS.value,
        {"group_id": int(group_id), "user_ids": [int(uid) for uid in user_ids]},
    )


@register_command(CommandType.SET_MEMBER_MUTE, require_group=False)
def handle_set_member_mute_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_ids = args.get("user_ids", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    muted = args.get("muted", False)
    if not isinstance(muted, bool):
        muted = bool(muted)
    if not group_id:
        raise ValueError("Missing: group_id")
    if not user_ids:
        raise ValueError("Missing: user_ids")
    return (
        CommandType.SET_MEMBER_MUTE.value,
        {"group_id": int(group_id), "user_ids": [int(uid) for uid in user_ids], "muted": muted},
    )


@register_command(CommandType.SET_GROUP_DND, require_group=False)
def handle_set_group_dnd_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    dnd = args.get("value", args.get("dnd", False))
    if not isinstance(dnd, bool):
        dnd = bool(dnd)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.SET_GROUP_DND.value,
        {"group_id": int(group_id), "dnd": dnd},
    )


@register_command(CommandType.SET_GROUP_TOP, require_group=False)
def handle_set_group_top_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    top = args.get("value", args.get("top", False))
    if not isinstance(top, bool):
        top = bool(top)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.SET_GROUP_TOP.value,
        {"group_id": int(group_id), "top": top},
    )


@register_command(CommandType.SET_GROUP_ALLOW_INVITE, require_group=False)
def handle_set_group_allow_invite_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    allow = args.get("value", args.get("allow", False))
    if not isinstance(allow, bool):
        allow = bool(allow)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.SET_GROUP_ALLOW_INVITE.value,
        {"group_id": int(group_id), "allow": allow},
    )


@register_command(CommandType.SET_GROUP_ALLOW_SHARE_CARD, require_group=False)
def handle_set_group_allow_share_card_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    allow = args.get("value", args.get("allow", False))
    if not isinstance(allow, bool):
        allow = bool(allow)
    if not group_id:
        raise ValueError("Missing: group_id")
    return (
        CommandType.SET_GROUP_ALLOW_SHARE_CARD.value,
        {"group_id": int(group_id), "allow": allow},
    )


@register_command(CommandType.ADD_GROUP_MANAGER, require_group=False)
def handle_add_group_manager_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_ids = args.get("user_ids", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    if not group_id:
        raise ValueError("Missing: group_id")
    if not user_ids:
        raise ValueError("Missing: user_ids")
    return (
        CommandType.ADD_GROUP_MANAGER.value,
        {"group_id": int(group_id), "user_ids": [int(uid) for uid in user_ids]},
    )


@register_command(CommandType.REMOVE_GROUP_MANAGER, require_group=False)
def handle_remove_group_manager_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    user_ids = args.get("user_ids", [])
    if not isinstance(user_ids, list):
        user_ids = [user_ids]
    if not group_id:
        raise ValueError("Missing: group_id")
    if not user_ids:
        raise ValueError("Missing: user_ids")
    return (
        CommandType.REMOVE_GROUP_MANAGER.value,
        {"group_id": int(group_id), "user_ids": [int(uid) for uid in user_ids]},
    )


@register_command(CommandType.SET_GROUP_TOP_MESSAGE, require_group=False)
def handle_set_group_top_message_command(args: Dict[str, Any], group_info) -> tuple:
    group_id = args.get("group_id")
    if not group_id and group_info:
        group_id = int(group_info.group_id)
    message_id = args.get("message_id")
    if not group_id:
        raise ValueError("Missing: group_id")
    if not message_id:
        raise ValueError("Missing: message_id")
    return (
        CommandType.SET_GROUP_TOP_MESSAGE.value,
        {"group_id": int(group_id), "message_id": int(message_id)},
    )

