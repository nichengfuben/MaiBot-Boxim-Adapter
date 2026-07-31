from typing import Any, Dict

from src.commands import CommandType
from src.send_handler.cmd_api.registry import register_command


@register_command(CommandType.LOAD_PRIVATE_OFFLINE_MESSAGE, require_group=False)
def handle_load_private_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.LOAD_PRIVATE_OFFLINE_MESSAGE.value, {"min_id": int(args.get("min_id", 0))})


@register_command(CommandType.LOAD_GROUP_OFFLINE_MESSAGE, require_group=False)
def handle_load_group_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.LOAD_GROUP_OFFLINE_MESSAGE.value, {"min_id": int(args.get("min_id", 0))})


@register_command(CommandType.LOAD_SYSTEM_OFFLINE_MESSAGE, require_group=False)
def handle_load_system_offline_message_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.LOAD_SYSTEM_OFFLINE_MESSAGE.value, {"min_seq_no": int(args.get("min_seq_no", 0))})

# ============ 贴纸/表情包 ============


@register_command(CommandType.GET_STICKER_ALBUMS, require_group=False)
def handle_get_sticker_albums_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_STICKER_ALBUMS.value, {})


@register_command(CommandType.GET_STICKERS, require_group=False)
def handle_get_stickers_command(args: Dict[str, Any], group_info) -> tuple:
    album_id = args.get("album_id")
    if not album_id:
        raise ValueError("Missing: album_id")
    return (CommandType.GET_STICKERS.value, {"album_id": int(album_id)})


@register_command(CommandType.SEARCH_STICKERS, require_group=False)
def handle_search_stickers_command(args: Dict[str, Any], group_info) -> tuple:
    name = args.get("name", "")
    if not name:
        raise ValueError("Missing: name")
    return (CommandType.SEARCH_STICKERS.value, {"name": str(name)})


@register_command(CommandType.GET_CUSTOM_STICKERS, require_group=False)
def handle_get_custom_stickers_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_CUSTOM_STICKERS.value, {})


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


@register_command(CommandType.DELETE_CUSTOM_STICKER, require_group=False)
def handle_delete_custom_sticker_command(args: Dict[str, Any], group_info) -> tuple:
    sticker_id = args.get("sticker_id")
    if not sticker_id:
        raise ValueError("Missing: sticker_id")
    return (CommandType.DELETE_CUSTOM_STICKER.value, {"sticker_id": int(sticker_id)})


@register_command(CommandType.TOP_CUSTOM_STICKER, require_group=False)
def handle_top_custom_sticker_command(args: Dict[str, Any], group_info) -> tuple:
    sticker_id = args.get("sticker_id")
    if not sticker_id:
        raise ValueError("Missing: sticker_id")
    return (CommandType.TOP_CUSTOM_STICKER.value, {"sticker_id": int(sticker_id)})

# ============ 投诉举报 ============


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


@register_command(CommandType.MARK_SYSTEM_READ, require_group=False)
def handle_mark_system_read_command(args: Dict[str, Any], group_info) -> tuple:
    max_seq_no = args.get("max_seq_no")
    if max_seq_no is None:
        raise ValueError("Missing: max_seq_no")
    return (CommandType.MARK_SYSTEM_READ.value, {"max_seq_no": int(max_seq_no)})


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


@register_command(CommandType.GET_REALNAME_AUTH_INFO, require_group=False)
def handle_get_realname_auth_info_command(args: Dict[str, Any], group_info) -> tuple:
    return (CommandType.GET_REALNAME_AUTH_INFO.value, {})


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
