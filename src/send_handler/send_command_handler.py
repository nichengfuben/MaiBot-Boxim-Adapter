from typing import Any, Dict, Callable, Optional

from src import CommandType


# Global command handler registry
_command_handlers: Dict[str, Dict[str, Any]] = {}


def register_command(command_type: CommandType, require_group: bool = True):
    """Decorator: register command handler"""

    def decorator(func: Callable) -> Callable:
        _command_handlers[command_type.value] = {
            "handler": func,
            "require_group": require_group,
        }
        return func

    return decorator


class SendCommandHandleClass:
    @classmethod
    def handle_command(cls, raw_command_data: Dict[str, Any], group_info: Optional[Any]):
        """Unified command processing entry

        Args:
            raw_command_data: Raw command data
            group_info: Group info (optional)

        Returns:
            Tuple[str, Dict[str, Any]]: (command_name, params) for BoxIM SDK execution

        Raises:
            RuntimeError: Unknown command or processing failure
        """
        command_name: str = raw_command_data.get("name")

        if command_name not in _command_handlers:
            raise RuntimeError(f"Unknown command type: {command_name}")

        try:
            handler_info = _command_handlers[command_name]
            handler = handler_info["handler"]
            require_group = handler_info["require_group"]

            if require_group and not group_info:
                raise ValueError(f"Command {command_name} requires group context")

            args = raw_command_data.get("args", {})
            return handler(args, group_info)

        except Exception as e:
            raise RuntimeError(f"Error processing command {command_name}: {str(e)}") from e

    # ============ Command Handlers ============

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.GET_LOGIN_INFO, require_group=False)
    def handle_get_login_info_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_LOGIN_INFO.value, {})

    @staticmethod
    @register_command(CommandType.GET_FRIEND_LIST, require_group=False)
    def handle_get_friend_list_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_FRIEND_LIST.value, {})

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.GET_GROUP_LIST, require_group=False)
    def handle_get_group_list_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_GROUP_LIST.value, {})

    # ============ 群组管理命令 ============

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.QUIT_GROUP, require_group=False)
    def handle_quit_group_command(args: Dict[str, Any], group_info) -> tuple:
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        if not group_id:
            raise ValueError("Missing: group_id")
        return (CommandType.QUIT_GROUP.value, {"group_id": int(group_id)})

    @staticmethod
    @register_command(CommandType.DELETE_GROUP, require_group=False)
    def handle_delete_group_command(args: Dict[str, Any], group_info) -> tuple:
        group_id = args.get("group_id")
        if not group_id:
            raise ValueError("Missing: group_id")
        return (CommandType.DELETE_GROUP.value, {"group_id": int(group_id)})

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.GET_ME, require_group=False)
    def handle_get_me_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_ME.value, {})

    @staticmethod
    @register_command(CommandType.GET_USER_INFO, require_group=False)
    def handle_get_user_info_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.SEARCH_USERS, require_group=False)
    def handle_search_users_command(args: Dict[str, Any], group_info) -> tuple:
        keyword = args.get("keyword", "")
        if not keyword:
            raise ValueError("Missing: keyword")
        return (CommandType.SEARCH_USERS.value, {"keyword": str(keyword)})

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.DELETE_FRIEND, require_group=False)
    def handle_delete_friend_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.DELETE_FRIEND.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.ADD_TO_BLACKLIST, require_group=False)
    def handle_add_to_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.ADD_TO_BLACKLIST.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.REMOVE_FROM_BLACKLIST, require_group=False)
    def handle_remove_from_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.REMOVE_FROM_BLACKLIST.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.GET_BLACKLIST, require_group=False)
    def handle_get_blacklist_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_BLACKLIST.value, {})

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.SET_MSG_EMOJI_LIKE, require_group=False)
    def handle_set_msg_emoji_like_command(args: Dict[str, Any], group_info) -> tuple:
        """BoxIM 不支持贴表情，标记为不支持"""
        return (CommandType.SET_MSG_EMOJI_LIKE.value, {"error": "BoxIM 不支持此功能"})

    @staticmethod
    @register_command(CommandType.GET_STRANGER_INFO, require_group=False)
    def handle_get_stranger_info_command(args: Dict[str, Any], group_info) -> tuple:
        """映射到 get_user_info"""
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.GET_GROUP_DETAIL_INFO, require_group=False)
    def handle_get_group_detail_info_command(args: Dict[str, Any], group_info) -> tuple:
        """映射到 get_group_info"""
        group_id = args.get("group_id")
        if not group_id and group_info:
            group_id = int(group_info.group_id)
        if not group_id:
            raise ValueError("Missing: group_id")
        return (CommandType.GET_GROUP_INFO.value, {"group_id": int(group_id)})

    @staticmethod
    @register_command(CommandType.GET_GROUP_MEMBER_INFO, require_group=False)
    def handle_get_group_member_info_command(args: Dict[str, Any], group_info) -> tuple:
        """映射到 get_user_info"""
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.GET_USER_INFO.value, {"user_id": int(user_id)})

    @staticmethod
    @register_command(CommandType.GET_MSG, require_group=False)
    def handle_get_msg_command(args: Dict[str, Any], group_info) -> tuple:
        """获取消息 - BoxIM 暂无直接获取单条消息 API"""
        return (CommandType.GET_MSG.value, {"error": "BoxIM 暂不支持"})

    @staticmethod
    @register_command(CommandType.GET_FORWARD_MSG, require_group=False)
    def handle_get_forward_msg_command(args: Dict[str, Any], group_info) -> tuple:
        """获取合并转发 - BoxIM 暂无此 API"""
        return (CommandType.GET_FORWARD_MSG.value, {"error": "BoxIM 暂不支持"})

    # ============ 好友设置命令 ============

    @staticmethod
    @register_command(CommandType.SET_FRIEND_DND, require_group=False)
    def handle_set_friend_dnd_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        value = args.get("value", args.get("dnd", False))
        if not isinstance(value, bool):
            value = bool(value)
        return (CommandType.SET_FRIEND_DND.value, {"user_id": int(user_id), "dnd": value})

    @staticmethod
    @register_command(CommandType.SET_FRIEND_TOP, require_group=False)
    def handle_set_friend_top_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        value = args.get("value", args.get("top", False))
        if not isinstance(value, bool):
            value = bool(value)
        return (CommandType.SET_FRIEND_TOP.value, {"user_id": int(user_id), "top": value})

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.GET_FRIEND_INFO, require_group=False)
    def handle_get_friend_info_command(args: Dict[str, Any], group_info) -> tuple:
        user_id = args.get("user_id")
        if not user_id:
            raise ValueError("Missing: user_id")
        return (CommandType.GET_FRIEND_INFO.value, {"user_id": int(user_id)})

    # ============ 好友请求 ============

    @staticmethod
    @register_command(CommandType.GET_FRIEND_REQUESTS, require_group=False)
    def handle_get_friend_requests_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_FRIEND_REQUESTS.value, {})

    @staticmethod
    @register_command(CommandType.ACCEPT_FRIEND_REQUEST, require_group=False)
    def handle_accept_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
        request_id = args.get("request_id")
        if not request_id:
            raise ValueError("Missing: request_id")
        return (CommandType.ACCEPT_FRIEND_REQUEST.value, {"request_id": int(request_id)})

    @staticmethod
    @register_command(CommandType.REJECT_FRIEND_REQUEST, require_group=False)
    def handle_reject_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
        request_id = args.get("request_id")
        if not request_id:
            raise ValueError("Missing: request_id")
        return (CommandType.REJECT_FRIEND_REQUEST.value, {"request_id": int(request_id)})

    @staticmethod
    @register_command(CommandType.RECALL_FRIEND_REQUEST, require_group=False)
    def handle_recall_friend_request_command(args: Dict[str, Any], group_info) -> tuple:
        request_id = args.get("request_id")
        if not request_id:
            raise ValueError("Missing: request_id")
        return (CommandType.RECALL_FRIEND_REQUEST.value, {"request_id": int(request_id)})

    # ============ 消息操作 ============

    @staticmethod
    @register_command(CommandType.DELETE_PRIVATE_MESSAGES, require_group=False)
    def handle_delete_private_messages_command(args: Dict[str, Any], group_info) -> tuple:
        chat_id = args.get("chat_id")
        message_ids = args.get("message_ids", [])
        if not chat_id:
            raise ValueError("Missing: chat_id")
        if not message_ids:
            raise ValueError("Missing: message_ids")
        return (CommandType.DELETE_PRIVATE_MESSAGES.value, {"chat_id": int(chat_id), "message_ids": [int(mid) for mid in message_ids]})

    @staticmethod
    @register_command(CommandType.DELETE_GROUP_MESSAGES, require_group=False)
    def handle_delete_group_messages_command(args: Dict[str, Any], group_info) -> tuple:
        chat_id = args.get("chat_id")
        message_ids = args.get("message_ids", [])
        if not chat_id:
            raise ValueError("Missing: chat_id")
        if not message_ids:
            raise ValueError("Missing: message_ids")
        return (CommandType.DELETE_GROUP_MESSAGES.value, {"chat_id": int(chat_id), "message_ids": [int(mid) for mid in message_ids]})

    @staticmethod
    @register_command(CommandType.DELETE_PRIVATE_CHAT, require_group=False)
    def handle_delete_private_chat_command(args: Dict[str, Any], group_info) -> tuple:
        chat_id = args.get("chat_id")
        if not chat_id:
            raise ValueError("Missing: chat_id")
        return (CommandType.DELETE_PRIVATE_CHAT.value, {"chat_id": int(chat_id)})

    @staticmethod
    @register_command(CommandType.DELETE_GROUP_CHAT, require_group=False)
    def handle_delete_group_chat_command(args: Dict[str, Any], group_info) -> tuple:
        chat_id = args.get("chat_id")
        if not chat_id:
            raise ValueError("Missing: chat_id")
        return (CommandType.DELETE_GROUP_CHAT.value, {"chat_id": int(chat_id)})

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.MARK_PRIVATE_READ, require_group=False)
    def handle_mark_private_read_command(args: Dict[str, Any], group_info) -> tuple:
        friend_id = args.get("friend_id")
        if not friend_id:
            raise ValueError("Missing: friend_id")
        result = {"friend_id": int(friend_id)}
        if args.get("message_id") is not None:
            result["message_id"] = int(args["message_id"])
        return (CommandType.MARK_PRIVATE_READ.value, result)

    @staticmethod
    @register_command(CommandType.MARK_GROUP_READ, require_group=False)
    def handle_mark_group_read_command(args: Dict[str, Any], group_info) -> tuple:
        group_id = args.get("group_id")
        if not group_id:
            raise ValueError("Missing: group_id")
        result = {"group_id": int(group_id)}
        if args.get("message_id") is not None:
            result["message_id"] = int(args["message_id"])
        return (CommandType.MARK_GROUP_READ.value, result)

    @staticmethod
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

    @staticmethod
    @register_command(CommandType.LOAD_PRIVATE_OFFLINE_MESSAGE, require_group=False)
    def handle_load_private_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.LOAD_PRIVATE_OFFLINE_MESSAGE.value, {"min_id": int(args.get("min_id", 0))})

    @staticmethod
    @register_command(CommandType.LOAD_GROUP_OFFLINE_MESSAGE, require_group=False)
    def handle_load_group_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.LOAD_GROUP_OFFLINE_MESSAGE.value, {"min_id": int(args.get("min_id", 0))})

    @staticmethod
    @register_command(CommandType.LOAD_SYSTEM_OFFLINE_MESSAGE, require_group=False)
    def handle_load_system_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.LOAD_SYSTEM_OFFLINE_MESSAGE.value, {"min_seq_no": int(args.get("min_seq_no", 0))})

    # ============ 贴纸/表情包 ============

    @staticmethod
    @register_command(CommandType.GET_STICKER_ALBUMS, require_group=False)
    def handle_get_sticker_albums_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_STICKER_ALBUMS.value, {})

    @staticmethod
    @register_command(CommandType.GET_STICKERS, require_group=False)
    def handle_get_stickers_command(args: Dict[str, Any], group_info) -> tuple:
        album_id = args.get("album_id")
        if not album_id:
            raise ValueError("Missing: album_id")
        return (CommandType.GET_STICKERS.value, {"album_id": int(album_id)})

    @staticmethod
    @register_command(CommandType.SEARCH_STICKERS, require_group=False)
    def handle_search_stickers_command(args: Dict[str, Any], group_info) -> tuple:
        name = args.get("name", "")
        if not name:
            raise ValueError("Missing: name")
        return (CommandType.SEARCH_STICKERS.value, {"name": str(name)})

    @staticmethod
    @register_command(CommandType.GET_CUSTOM_STICKERS, require_group=False)
    def handle_get_custom_stickers_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_CUSTOM_STICKERS.value, {})

    @staticmethod
    @register_command(CommandType.ADD_CUSTOM_STICKER, require_group=False)
    def handle_add_custom_sticker_command(args: Dict[str, Any], group_info) -> tuple:
        name = args.get("name")
        image_url = args.get("image_url")
        if not name or not image_url:
            raise ValueError("Missing: name or image_url")
        return (
            CommandType.ADD_CUSTOM_STICKER.value,
            {
                "name": str(name), "image_url": str(image_url),
                "thumb_url": str(args.get("thumb_url", image_url)),
                "width": int(args.get("width", 100)),
                "height": int(args.get("height", 100)),
            },
        )

    @staticmethod
    @register_command(CommandType.DELETE_CUSTOM_STICKER, require_group=False)
    def handle_delete_custom_sticker_command(args: Dict[str, Any], group_info) -> tuple:
        sticker_id = args.get("sticker_id")
        if not sticker_id:
            raise ValueError("Missing: sticker_id")
        return (CommandType.DELETE_CUSTOM_STICKER.value, {"sticker_id": int(sticker_id)})

    @staticmethod
    @register_command(CommandType.TOP_CUSTOM_STICKER, require_group=False)
    def handle_top_custom_sticker_command(args: Dict[str, Any], group_info) -> tuple:
        sticker_id = args.get("sticker_id")
        if not sticker_id:
            raise ValueError("Missing: sticker_id")
        return (CommandType.TOP_CUSTOM_STICKER.value, {"sticker_id": int(sticker_id)})

    # ============ 投诉举报 ============

    @staticmethod
    @register_command(CommandType.SUBMIT_COMPLAINT, require_group=False)
    def handle_submit_complaint_command(args: Dict[str, Any], group_info) -> tuple:
        target_type = args.get("target_type")
        target_id = args.get("target_id")
        content = args.get("content", "")
        if not target_type or not target_id:
            raise ValueError("Missing: target_type or target_id")
        return (
            CommandType.SUBMIT_COMPLAINT.value,
            {
                "target_type": str(target_type), "target_id": int(target_id),
                "complaint_type": int(args.get("complaint_type", 99)),
                "content": str(content)[:512],
                "target_name": str(args.get("target_name", "")),
                "images": args.get("images", []),
            },
        )

    # ============ 系统消息 ============

    @staticmethod
    @register_command(CommandType.MARK_SYSTEM_READ, require_group=False)
    def handle_mark_system_read_command(args: Dict[str, Any], group_info) -> tuple:
        max_seq_no = args.get("max_seq_no")
        if max_seq_no is None:
            raise ValueError("Missing: max_seq_no")
        return (CommandType.MARK_SYSTEM_READ.value, {"max_seq_no": int(max_seq_no)})

    @staticmethod
    @register_command(CommandType.GET_SYSTEM_MESSAGE_CONTENT, require_group=False)
    def handle_get_system_message_content_command(args: Dict[str, Any], group_info) -> tuple:
        message_id = args.get("message_id")
        if not message_id:
            raise ValueError("Missing: message_id")
        return (CommandType.GET_SYSTEM_MESSAGE_CONTENT.value, {"message_id": int(message_id)})

    # === 个人资料 ===

    @register_command(CommandType.UPDATE_PROFILE, require_group=False)
    def handle_update_profile_command(args: Dict[str, Any], group_info) -> tuple:
        fields = {}
        for key in ("signature", "nickName", "sex", "headImage"):
            if key in args:
                fields[key] = args[key]
        if not fields:
            raise ValueError("Missing profile fields (signature/nickName/sex/headImage)")
        return (CommandType.UPDATE_PROFILE.value, fields)

    # === 实名认证 ===

    @staticmethod
    @register_command(CommandType.GET_REALNAME_AUTH_INFO, require_group=False)
    def handle_get_realname_auth_info_command(args: Dict[str, Any], group_info) -> tuple:
        return (CommandType.GET_REALNAME_AUTH_INFO.value, {})

    @staticmethod
    @register_command(CommandType.SUBMIT_REALNAME_AUTH, require_group=False)
    def handle_submit_realname_auth_command(args: Dict[str, Any], group_info) -> tuple:
        real_name = args.get("real_name")
        id_card = args.get("id_card")
        if not real_name:
            raise ValueError("Missing: real_name")
        if not id_card:
            raise ValueError("Missing: id_card")
        return (
            CommandType.SUBMIT_REALNAME_AUTH.value,
            {"real_name": str(real_name), "id_card": str(id_card)},
        )
