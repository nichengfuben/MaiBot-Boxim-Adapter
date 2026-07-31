from typing import Any, Dict, Callable, Optional

from src.commands import CommandType


_command_handlers: Dict[str, Dict[str, Any]] = {}


def register_command(command_type: CommandType, require_group: bool = True):
    """Decorator: register command handler."""

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
            raise RuntimeError(
                f"Error processing command {command_name}: {str(e)}"
            ) from e
