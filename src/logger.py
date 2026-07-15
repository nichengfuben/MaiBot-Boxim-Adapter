from echotools import configure, get_logger
from pathlib import Path
from datetime import datetime
import logging

# 日志目录配置
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 清理过期日志
try:
    cutoff = datetime.now().timestamp() - 30 * 86400
    for log_file in LOG_DIR.glob("*.log"):
        if log_file.stat().st_mtime < cutoff:
            log_file.unlink()
except Exception:
    pass

# 配置 echotools 全局日志
log_file = LOG_DIR / f"adapter_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
configure(
    level="INFO",
    color=True,
    log_file=str(log_file),
    max_bytes=100 * 1024 * 1024,
    backup_count=5,
)

def _unify_external_loggers() -> None:
    """清除所有已知的 SDK / 第三方库 logger 的独立 handler，
    让它们统一通过 root logger (echotools) 输出，确保日志风格一致。"""
    _names = [
        "boxim", "boxim.client", "boxim.transport",
        "engineio", "engineio.client",
        "socketio", "socketio.client",
        "aiohttp", "aiohttp.access", "aiohttp.client", "aiohttp.server",
        "maim_message",
        "maim_message.ws_config",
        "maim_message.client_base",
        "maim_message.message_cache",
        "maim_message.connection_interface",
        "uvicorn", "uvicorn.error", "uvicorn.access", "uvicorn.asgi",
    ]
    for name in _names:
        _lg = logging.getLogger(name)
        _lg.handlers.clear()
        _lg.propagate = True
        _lg.setLevel(logging.NOTSET)

    try:
        import maim_message.log_utils as _mu
        _mu._logger = logging.getLogger("maim_message")
    except (ImportError, AttributeError):
        pass


# 默认 logger 实例
logger = get_logger("Adapter")
custom_logger = get_logger("maim_message")
