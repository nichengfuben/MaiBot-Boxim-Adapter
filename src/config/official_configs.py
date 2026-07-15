from dataclasses import dataclass, field
from typing import Literal

from src.config.config_base import ConfigBase

"""
须知：
1. 本文件中记录了所有的配置项
2. 所有新增的class都需要继承自ConfigBase
3. 所有新增的class都应在config.py中的Config类中添加字段
4. 对于新增的字段，若为可选项，则应在其后添加field()并设置default_factory或default
"""

ADAPTER_PLATFORM = "boxim"


@dataclass
class NicknameConfig(ConfigBase):
    nickname: str
    """机器人昵称"""


@dataclass
class BoxIMConfig(ConfigBase):
    """BoxIM 账户连接设置"""

    username: str = ""
    """BoxIM 账号用户名/邮箱/手机号"""

    password: str = ""
    """BoxIM 账号密码"""

    base_url: str = "https://www.boxim.online"
    """BoxIM API 根地址"""

    ws_url: str = "wss://www.boxim.online/im"
    """BoxIM WebSocket 地址"""

    heartbeat_interval: int = 30
    """心跳间隔时间，单位为秒，用于 echo 响应超时清理"""


@dataclass
class MaiBotServerConfig(ConfigBase):
    platform_name: str = field(default=ADAPTER_PLATFORM, init=False)
    """平台名称，固定为 'boxim'"""

    host: str = "localhost"
    """MaiMCore的主机地址"""

    port: int = 8000
    """MaiMCore的端口号"""

    enable_api_server: bool = False
    """是否启用API-Server模式连接（需 maim_message >= 0.7.5）"""

    base_url: str = ""
    """API-Server连接地址 (ws://ip:port/path)"""

    api_key: str = ""
    """API Key（仅在 enable_api_server 为 True 时使用）"""


@dataclass
class ChatConfig(ConfigBase):
    group_list_type: Literal["whitelist", "blacklist"] = "blacklist"
    """群聊列表类型 白名单/黑名单"""

    group_list: list[int] = field(default_factory=list)
    """群聊列表"""

    private_list_type: Literal["whitelist", "blacklist"] = "blacklist"
    """私聊列表类型 白名单/黑名单"""

    private_list: list[int] = field(default_factory=list)
    """私聊列表"""

    ban_user_id: list[int] = field(default_factory=list)
    """全局禁止交互的用户ID列表"""


@dataclass
class MediaConfig(ConfigBase):
    """媒体文件下载设置"""

    download_timeout: int = 30
    """下载图片/语音/视频等媒体的超时时间（秒）"""


@dataclass
class StickerConfig(ConfigBase):
    """贴纸（表情包）处理设置"""

    download_as_emoji: bool = True
    """接收到贴纸消息时，是否下载为图片并以 emoji Seg 发送到麦麦"""


@dataclass
class VoiceConfig(ConfigBase):
    use_tts: bool = True
    """是否处理语音消息"""


@dataclass
class DebugConfig(ConfigBase):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    """日志级别，默认为INFO"""
