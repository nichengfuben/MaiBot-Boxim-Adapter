from enum import Enum
import tomlkit
import os
from .logger import logger


class CommandType(Enum):
    """命令类型（BoxIM 支持的命令）"""

    # 操作类命令
    GROUP_BAN = "set_group_ban"  # 禁言用户（映射到群全体禁言）
    GROUP_WHOLE_BAN = "set_group_whole_ban"  # 群全体禁言
    GROUP_KICK = "set_group_kick"  # 踢出群聊（映射到 remove_group_members）
    GROUP_KICK_MEMBERS = "set_group_kick_members"  # 批量踢出群成员
    SET_GROUP_NAME = "set_group_name"  # 设置群名
    DELETE_MSG = "delete_msg"  # 撤回消息
    SET_MSG_EMOJI_LIKE = "set_msg_emoji_like"  # 给消息贴表情（BoxIM不支持）

    # 群组管理命令
    CREATE_GROUP = "create_group"
    MODIFY_GROUP_NOTICE = "modify_group_notice"
    QUIT_GROUP = "quit_group"
    DELETE_GROUP = "delete_group"
    INVITE_TO_GROUP = "invite_to_group"
    REMOVE_GROUP_MEMBERS = "remove_group_members"
    SET_MEMBER_MUTE = "set_member_mute"
    SET_GROUP_DND = "set_group_dnd"
    SET_GROUP_TOP = "set_group_top"
    SET_GROUP_ALLOW_INVITE = "set_group_allow_invite"
    SET_GROUP_ALLOW_SHARE_CARD = "set_group_allow_share_card"
    ADD_GROUP_MANAGER = "add_group_manager"
    REMOVE_GROUP_MANAGER = "remove_group_manager"
    SET_GROUP_TOP_MESSAGE = "set_group_top_message"
    REMOVE_GROUP_TOP_MESSAGE = "remove_group_top_message"
    HIDE_GROUP_TOP_MESSAGE = "hide_group_top_message"

    # 查询类命令
    GET_LOGIN_INFO = "get_login_info"
    GET_STRANGER_INFO = "get_stranger_info"
    GET_FRIEND_LIST = "get_friend_list"
    GET_FRIEND_INFO = "get_friend_info"
    GET_GROUP_INFO = "get_group_info"
    GET_GROUP_DETAIL_INFO = "get_group_detail_info"
    GET_GROUP_LIST = "get_group_list"
    GET_GROUP_MEMBER_INFO = "get_group_member_info"
    GET_GROUP_MEMBER_LIST = "get_group_member_list"
    GET_GROUP_ONLINE_MEMBERS = "get_group_online_members"
    GET_GROUP_MESSAGE_READERS = "get_group_message_readers"
    GET_MSG = "get_msg"
    GET_FORWARD_MSG = "get_forward_msg"
    GET_ME = "get_me"
    GET_USER_INFO = "get_user_info"
    SEARCH_USERS = "search_users"

    # 好友管理
    ADD_FRIEND = "add_friend"
    DELETE_FRIEND = "delete_friend"
    SET_FRIEND_DND = "set_friend_dnd"
    SET_FRIEND_TOP = "set_friend_top"
    UPDATE_FRIEND_REMARK = "update_friend_remark"

    # 好友请求
    GET_FRIEND_REQUESTS = "get_friend_requests"
    ACCEPT_FRIEND_REQUEST = "accept_friend_request"
    REJECT_FRIEND_REQUEST = "reject_friend_request"
    RECALL_FRIEND_REQUEST = "recall_friend_request"

    # 黑名单
    ADD_TO_BLACKLIST = "add_to_blacklist"
    REMOVE_FROM_BLACKLIST = "remove_from_blacklist"
    GET_BLACKLIST = "get_blacklist"

    # 加入群
    JOIN_GROUP = "join_group"

    # 消息操作
    DELETE_PRIVATE_MESSAGES = "delete_private_messages"
    DELETE_GROUP_MESSAGES = "delete_group_messages"
    DELETE_PRIVATE_CHAT = "delete_private_chat"
    DELETE_GROUP_CHAT = "delete_group_chat"
    GET_PRIVATE_MESSAGE_HISTORY = "get_private_message_history"
    GET_GROUP_MESSAGE_HISTORY = "get_group_message_history"
    MARK_PRIVATE_READ = "mark_private_read"
    MARK_GROUP_READ = "mark_group_read"

    # 离线消息
    LOAD_PRIVATE_OFFLINE_MESSAGE = "load_private_offline_message"
    LOAD_GROUP_OFFLINE_MESSAGE = "load_group_offline_message"
    LOAD_SYSTEM_OFFLINE_MESSAGE = "load_system_offline_message"

    # 贴纸/表情包
    GET_STICKER_ALBUMS = "get_sticker_albums"
    GET_STICKERS = "get_stickers"
    SEARCH_STICKERS = "search_stickers"
    GET_CUSTOM_STICKERS = "get_custom_stickers"
    ADD_CUSTOM_STICKER = "add_custom_sticker"
    DELETE_CUSTOM_STICKER = "delete_custom_sticker"
    TOP_CUSTOM_STICKER = "top_custom_sticker"

    # 投诉举报
    SUBMIT_COMPLAINT = "submit_complaint"

    # 系统消息
    MARK_SYSTEM_READ = "mark_system_read"
    GET_SYSTEM_MESSAGE_CONTENT = "get_system_message_content"

    # 个人资料
    UPDATE_PROFILE = "update_profile"

    def __str__(self) -> str:
        return self.value


pyproject_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
toml_data = tomlkit.parse(open(pyproject_path, "r", encoding="utf-8").read())
version = toml_data["project"]["version"]
logger.info(f"\nMaiBot-Boxim-Adapter 版本: {version}\n")
