import asyncio
import signal
import sys
import json

from sdk import BoxIM
from src.runtime.logger import logger
from src.recv_handler.message_handler import message_handler
from src.recv_handler.meta_handler import meta_handler
from src.recv_handler.notice_handler import notice_handler
from src.runtime.mmc_layer import mmc_start_com
from src.runtime.response import check_timeout_response
from src.runtime.lifecycle import (
    boxim_client,
    message_queue,
    mmc_ready,
    init_boxim,
    graceful_shutdown,
    version_watch,
)
from src.config import config_manager

_shutdown_event: asyncio.Event | None = None


async def boxim_message_handler(msg_data, is_group):
    """Handle messages received from BoxIM WebSocket."""
    try:
        message_id = msg_data.get("id")
        msg_type = msg_data.get("type", 0)
        if message_id is None:
            no_id = {11, 12, 53, 54, 82} | set(range(100, 111)) | set(range(200, 213))
            if msg_type in no_id:
                msg_data["post_type"] = "notice"
                msg_data["notice_type"] = "notify"
                await notice_handler.handle_notice(msg_data)
                return
            logger.warning(
                f"BoxIM 消息缺少 id, type={msg_type}, keys={list(msg_data.keys())}, "
                f"data={json.dumps(msg_data, ensure_ascii=False)}"
            )
            return
        await message_handler.handle_boxim_message(msg_data, is_group)
    except Exception as e:
        logger.error(f"Error handling BoxIM message: {e}")
        import traceback

        logger.error(traceback.format_exc())


async def message_process():
    """Process messages from the queue."""
    await mmc_ready.wait()
    while True:
        message = await message_queue.get()
        post_type = message.get("post_type")
        if post_type == "message":
            await message_handler.handle_boxim_message(
                message, message.get("is_group", False)
            )
        elif post_type == "meta_event":
            await meta_handler.handle_meta_event(message)
        elif post_type == "notice":
            await notice_handler.handle_notice(message)
        else:
            logger.warning(f"Unknown post_type: {post_type}")
        message_queue.task_done()


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.warning("收到退出信号，正在优雅关闭...")
        if _shutdown_event and not _shutdown_event.is_set():
            _shutdown_event.set()

    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
        return

    def _win_handler(signum, frame):
        _signal_handler()

    signal.signal(signal.SIGTERM, _win_handler)


async def _wait_for_shutdown_signal() -> None:
    if _shutdown_event:
        await _shutdown_event.wait()
    else:
        await asyncio.Event().wait()


async def main():
    _install_signal_handlers(asyncio.get_running_loop())
    asyncio.create_task(config_manager.start_watch())
    backoff = 1
    attempt = 0
    while True:
        attempt += 1
        try:
            await init_boxim(boxim_message_handler)
            break
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"BoxIM 连接失败 (第 {attempt} 次): {e}")
            logger.info(f"{backoff} 秒后重试...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)
    tasks = [
        asyncio.create_task(mmc_start_com()),
        asyncio.create_task(message_process()),
        asyncio.create_task(check_timeout_response()),
        asyncio.create_task(version_watch()),
        asyncio.create_task(_wait_for_shutdown_signal()),
    ]
    done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        exc = task.exception()
        if exc and not isinstance(exc, asyncio.CancelledError):
            logger.error(f"核心任务异常退出: {exc}")


if __name__ == "__main__":
    import gc
    import warnings

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
        try:
            loop.run_until_complete(graceful_shutdown(silent=False))
        except Exception:
            pass
    except KeyboardInterrupt:
        logger.warning("收到中断信号，正在优雅关闭...")
        try:
            loop.run_until_complete(graceful_shutdown(silent=False))
        except Exception:
            pass
    except Exception as e:
        logger.error(f"主程序异常: {str(e)}")
        try:
            loop.run_until_complete(graceful_shutdown(silent=True))
        except Exception:
            pass
        sys.exit(1)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        finally:
            gc.collect()
            warnings.filterwarnings("ignore", category=ResourceWarning)
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            if loop and not loop.is_closed():
                loop.close()
        sys.exit(0)
