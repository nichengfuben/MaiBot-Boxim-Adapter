import os
import tomlkit

from src.commands import CommandType
from src.runtime.logger import logger

__all__ = ["CommandType"]

pyproject_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pyproject.toml")
toml_data = tomlkit.parse(open(pyproject_path, "r", encoding="utf-8").read())
version = toml_data["project"]["version"]
logger.info(f"\nMaiBot-Boxim-Adapter 版本: {version}\n")
