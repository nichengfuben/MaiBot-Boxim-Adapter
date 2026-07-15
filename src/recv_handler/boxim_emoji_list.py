# BoxIM 贴纸（表情包）列表
# 从 sdk 统一数据源导入，避免重复维护

from sdk import (
    EMOJI_NAMES as BOXIM_STICKER_NAMES,
    EMOJI_NAME_TO_INDEX as STICKER_NAME_TO_ID,
    EMOJI_PATTERN as _INLINE_PATTERN,
)

# sticker_id (str) -> 文本描述，类似 qq_face
boxim_face: dict[str, str] = {
    str(idx): f"[表情：{name}]"
    for idx, name in enumerate(BOXIM_STICKER_NAMES)
}

# 匹配文本中内联表情的正则
INLINE_STICKER_PATTERN = _INLINE_PATTERN.pattern
