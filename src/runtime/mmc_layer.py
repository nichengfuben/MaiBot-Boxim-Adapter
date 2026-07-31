from maim_message import Router, RouteConfig, TargetConfig, MessageBase
from src.config import global_config
from src.runtime.logger import logger, custom_logger, _unify_external_loggers
from src.send_handler.dispatch import send_handler
from src.recv_handler.message_sending import message_send_instance
from maim_message.client import create_client_config, WebSocketClient
from maim_message.message import APIMessageBase
from typing import Callable, Dict, Any
import asyncio
import importlib.metadata

# Check maim_message version for MessageConverter support (>= 0.7.5)
try:
    maim_message_version = importlib.metadata.version("maim_message")
    version_int = [int(x) for x in maim_message_version.split(".")]
    HAS_MESSAGE_CONVERTER = version_int >= [0, 7, 5]
except (importlib.metadata.PackageNotFoundError, ValueError):
    HAS_MESSAGE_CONVERTER = False

router = None


class APIServerWrapper:
    """Wrapper to make WebSocketClient compatible with legacy Router interface"""

    def __init__(self, client: WebSocketClient):
        self.client = client
        self.platform = global_config.maibot_server.platform_name

    def register_class_handler(self, handler):
        pass

    async def send_message(self, message: MessageBase) -> bool:
        from maim_message import MessageConverter

        api_message = MessageConverter.to_api_receive(
            message=message,
            api_key=global_config.maibot_server.api_key,
            platform=message.message_info.platform or self.platform,
        )
        return await self.client.send_message(api_message)

    async def send_custom_message(self, platform: str, message_type_name: str, message: Dict) -> bool:
        return await self.client.send_custom_message(message_type_name, message)

    async def run(self):
        await self.client.start()
        await self.client.connect()

    async def stop(self):
        await self.client.stop()


# Global communication object
router = None


async def _on_api_message(message: APIMessageBase, metadata: Dict[str, Any]):
    try:
        from maim_message import MessageConverter
        legacy_message = MessageConverter.from_api_send(message)
        await send_handler.handle_message(legacy_message.to_dict())
    except Exception as e:
        logger.error(f"Message bridge conversion failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def _signal_ready_when(check: Callable[[], bool], label: str) -> None:
    """等 MaiBot WebSocket 真正连上后再开放消息队列。"""
    from src.runtime.lifecycle import mmc_ready

    while not check():
        await asyncio.sleep(0.1)
    mmc_ready.set()
    logger.info(f"MMC {label} 已连接，开始处理消息队列")


async def _start_api_mode(config) -> None:
    global router
    client_config = create_client_config(
        url=config.base_url,
        api_key=config.api_key,
        platform=config.platform_name,
        on_message=_on_api_message,
        custom_logger=custom_logger,
    )
    client = WebSocketClient(client_config)
    router = APIServerWrapper(client)
    _unify_external_loggers()
    message_send_instance.maibot_router = router
    ready_task = asyncio.create_task(
        _signal_ready_when(client.is_connected, "API WebSocket")
    )
    try:
        await router.run()
        # connect() 返回后连接由后台维持；保持任务存活避免主循环误判退出
        while True:
            await asyncio.sleep(3600)
    finally:
        ready_task.cancel()


async def _start_legacy_mode(config) -> None:
    global router
    platform = config.platform_name
    route_config = RouteConfig(
        route_config={
            platform: TargetConfig(
                url=f"ws://{config.host}:{config.port}/ws",
                token=None,
            )
        }
    )
    router = Router(route_config, custom_logger)
    _unify_external_loggers()
    router.register_class_handler(send_handler.handle_message)
    message_send_instance.maibot_router = router
    ready_task = asyncio.create_task(
        _signal_ready_when(lambda: router.check_connection(platform), "WebSocket")
    )
    try:
        await router.run()
    finally:
        ready_task.cancel()


async def mmc_start_com():
    config = global_config.maibot_server
    if config.enable_api_server and HAS_MESSAGE_CONVERTER:
        logger.info("Using API-Server mode to connect to MaiBot")
        await _start_api_mode(config)
        return
    logger.info("Using Legacy WebSocket mode to connect to MaiBot")
    await _start_legacy_mode(config)


async def mmc_stop_com():
    if router:
        await router.stop()
