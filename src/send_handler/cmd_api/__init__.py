"""Command parse package: import side-effects register handlers."""

from src.send_handler.cmd_api.registry import SendCommandHandleClass, register_command
from src.send_handler.cmd_api import group as _group  # noqa: F401
from src.send_handler.cmd_api import group_set as _group_set  # noqa: F401
from src.send_handler.cmd_api import social as _social  # noqa: F401
from src.send_handler.cmd_api import message as _message  # noqa: F401
from src.send_handler.cmd_api import extra as _extra  # noqa: F401

__all__ = ["SendCommandHandleClass", "register_command"]
