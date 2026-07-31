from src.runtime.logger import logger
from src.config import global_config
import time
import asyncio

from . import MetaEventType


class MetaEventHandler:
    def __init__(self):
        self.interval = global_config.boxim.heartbeat_interval
        self._interval_checking = False
        self.last_heart_beat: float = 0

    async def handle_meta_event(self, message: dict) -> None:
        event_type = message.get("meta_event_type")
        if event_type == MetaEventType.lifecycle:
            sub_type = message.get("sub_type")
            if sub_type == MetaEventType.Lifecycle.connect:
                self_id = message.get("self_id")
                self.last_heart_beat = time.time()
                logger.info(f"Bot {self_id} BoxIM 连接成功")
                asyncio.create_task(self.check_heartbeat(self_id))
        elif event_type == MetaEventType.heartbeat:
            self_id = message.get("self_id")
            status = message.get("status", {})
            is_online = status.get("online", False)
            is_good = status.get("good", False)

            if is_online and is_good:
                if not self._interval_checking:
                    asyncio.create_task(self.check_heartbeat(self_id))
                self.last_heart_beat = time.time()
                self.interval = message.get("interval", 30000) / 1000
            else:
                if not is_online:
                    logger.error(f"Bot {self_id} 已下线 (online=false)")
                elif not is_good:
                    logger.warning(f"Bot {self_id} 状态异常 (good=false)")

    async def check_heartbeat(self, id: int) -> None:
        self._interval_checking = True
        while True:
            now_time = time.time()
            if now_time - self.last_heart_beat > self.interval * 2:
                logger.error(f"Bot {id} 可能发生了连接断开或被下线！")
                break
            else:
                logger.debug("心跳正常")
            await asyncio.sleep(self.interval)


meta_handler = MetaEventHandler()
