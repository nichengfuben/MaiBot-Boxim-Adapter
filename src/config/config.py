import os
import sys
from dataclasses import dataclass
from datetime import datetime

import tomlkit
import shutil

from tomlkit import TOMLDocument
from tomlkit.items import Table
from rich.traceback import install

from src.config.config_base import ConfigBase
from src.config.official_configs import (
    BoxIMConfig,
    ChatConfig,
    DebugConfig,
    MaiBotServerConfig,
    MediaConfig,
    NicknameConfig,
    StickerConfig,
    VoiceConfig,
)

install(extra_lines=3)

TEMPLATE_DIR = "template"


def _restart_process():
    print("[Config] 正在自动重启适配器...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def get_template_version():
    template_path = f"{TEMPLATE_DIR}/template_config.toml"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = tomlkit.load(f)
        return data.get("inner", {}).get("version")
    except Exception:
        return None


def get_current_config_version():
    try:
        with open("config.toml", "r", encoding="utf-8") as f:
            data = tomlkit.load(f)
        return data.get("inner", {}).get("version")
    except Exception:
        return None


def update_config():
    from src.logger import logger

    template_path = f"{TEMPLATE_DIR}/template_config.toml"
    old_config_path = "config.toml"
    new_config_path = "config.toml"

    if not os.path.exists(old_config_path):
        logger.info("配置文件不存在，从模板创建新配置")
        shutil.copy2(template_path, old_config_path)
        logger.info(f"已创建新配置文件，请填写后重新运行: {old_config_path}")
        quit()

    with open(old_config_path, "r", encoding="utf-8") as f:
        old_config = tomlkit.load(f)
    with open(template_path, "r", encoding="utf-8") as f:
        new_config = tomlkit.load(f)

    if old_config and "inner" in old_config and "inner" in new_config:
        old_version = old_config["inner"].get("version")
        new_version = new_config["inner"].get("version")
        if old_version and new_version and old_version == new_version:
            logger.info(f"检测到配置文件版本号相同 (v{old_version})，跳过更新")
            return
        else:
            logger.info(f"检测到版本号不同: 旧版本 v{old_version} -> 新版本 v{new_version}")
    else:
        logger.info("已有配置文件未检测到版本号，可能是旧版本。将进行更新")

    backup_dir = "config_backup"
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    old_backup_path = os.path.join(backup_dir, f"config.toml.bak.{timestamp}")

    shutil.copy2(old_config_path, old_backup_path)
    logger.info(f"已备份旧配置文件到: {old_backup_path}")

    shutil.copy2(template_path, new_config_path)
    logger.info(f"已创建新配置文件: {new_config_path}")

    def update_dict(target: TOMLDocument | dict, source: TOMLDocument | dict):
        for key, value in source.items():
            if key == "version":
                continue
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], (dict, Table)):
                    update_dict(target[key], value)
                else:
                    try:
                        if isinstance(value, list):
                            target[key] = tomlkit.array(str(value)) if value else tomlkit.array()
                        else:
                            target[key] = tomlkit.item(value)
                    except (TypeError, ValueError):
                        target[key] = value

    logger.info("开始合并新旧配置...")
    update_dict(new_config, old_config)

    with open(new_config_path, "w", encoding="utf-8") as f:
        f.write(tomlkit.dumps(new_config))
    logger.info("配置文件更新完成，建议检查新配置文件中的内容，以免丢失重要信息")
    _restart_process()


@dataclass
class Config(ConfigBase):
    """总配置类"""

    nickname: NicknameConfig
    boxim: BoxIMConfig
    maibot_server: MaiBotServerConfig
    chat: ChatConfig
    media: MediaConfig
    sticker: StickerConfig
    voice: VoiceConfig
    debug: DebugConfig


def load_config(config_path: str) -> Config:
    from src.logger import logger

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = tomlkit.load(f)

    try:
        return Config.from_dict(config_data)
    except Exception as e:
        logger.error(f"配置文件解析失败: {e}")
        raise e


update_config()

from src.logger import logger

logger.info("正在品鉴配置文件...")

from .config_manager import ConfigManager

_config_manager = ConfigManager()
_config_manager.load(config_path="config.toml")

global_config = _config_manager

logger.info("非常的新鲜，非常的美味！")
