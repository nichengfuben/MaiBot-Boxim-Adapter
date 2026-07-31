"""BoxIM init / shutdown / version watch lifecycle helpers."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

from sdk import BoxIM
from src.config import global_config
from src.recv_handler.message_handler import message_handler
from src.runtime.logger import logger, _unify_external_loggers
from src.runtime.mmc_layer import mmc_stop_com
from src.send_handler.im_sending import boxim_message_sender

boxim_client: Optional[BoxIM] = None
message_queue: asyncio.Queue = asyncio.Queue()
mmc_ready = asyncio.Event()


async def version_watch() -> None:
    """定期检查模板版本，检测到新版本时自动更新配置并重启。"""
    from src.config.config import (
        get_template_version,
        get_current_config_version,
        update_config,
    )

    while True:
        await asyncio.sleep(60)
        try:
            template_ver = get_template_version()
            current_ver = get_current_config_version()
            if template_ver and current_ver and template_ver != current_ver:
                logger.info(
                    f"检测到新版本: v{current_ver} -> v{template_ver}，准备自动更新..."
                )
                await graceful_shutdown(silent=False)
                update_config()
        except Exception as e:
            logger.debug(f"版本检查异常: {e}")


async def init_boxim(on_message) -> BoxIM:
    """Initialize BoxIM SDK and connect."""
    global boxim_client
    config = global_config.boxim
    logger.info(f"Initializing BoxIM SDK: {config.base_url}")
    boxim_client = BoxIM(
        base_url=config.base_url,
        ws_url=config.ws_url,
        auto_refresh_token=True,
        debug=global_config.debug.level == "DEBUG",
    )
    _unify_external_loggers()
    await boxim_client.alogin(config.username, config.password)
    logger.info(f"BoxIM login successful: {config.username}")
    await _setup_bot_info(config.username)
    boxim_message_sender.set_boxim_client(boxim_client)
    message_handler.set_boxim_client(boxim_client)
    boxim_client.on_message(on_message)
    asyncio.create_task(boxim_client.start_listening())
    logger.info("BoxIM WebSocket listener started")
    await _load_offline_messages()
    return boxim_client


async def _setup_bot_info(fallback_name: str) -> None:
    try:
        self_info = await boxim_client.aget_me()
        bot_user_id = self_info.get("id", 0)
        bot_nickname = (
            self_info.get("nickName") or self_info.get("userName") or fallback_name
        )
        message_handler.set_bot_info(bot_user_id, bot_nickname)
        logger.info(f"Bot 自身信息: user_id={bot_user_id}, nickname={bot_nickname!r}")
    except Exception as e:
        logger.warning(f"获取 bot 自身信息失败，使用登录用户名作为昵称: {e}")
        message_handler.set_bot_info(0, fallback_name)


async def _load_offline_messages() -> None:
    state_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "data",
        "offline_state.json",
    )
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    last_private_id = 0
    last_group_id = 0
    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                last_private_id = state.get("last_private_id", 0)
                last_group_id = state.get("last_group_id", 0)
            logger.info(
                f"离线状态恢复: private_id={last_private_id}, group_id={last_group_id}"
            )
    except Exception as e:
        logger.debug(f"读取离线状态文件失败，从头开始: {e}")
    message_handler.init_offline_state(state_file, last_private_id, last_group_id)
    offline_count = 0
    offline_count += await _enqueue_offline(False, last_private_id)
    offline_count += await _enqueue_offline(True, last_group_id)
    if offline_count > 0:
        logger.info(
            f"已将 {offline_count} 条离线消息放入队列 "
            f"(private>{last_private_id}, group>{last_group_id})"
        )


async def _enqueue_offline(is_group: bool, min_id: int) -> int:
    try:
        if is_group:
            msgs = await boxim_client.aload_group_offline_message(min_id)
        else:
            msgs = await boxim_client.aload_private_offline_message(min_id)
        if not msgs:
            return 0
        for msg in msgs:
            msg["post_type"] = "message"
            msg["is_group"] = is_group
            await message_queue.put(msg)
        return len(msgs)
    except Exception as e:
        kind = "群聊" if is_group else "私聊"
        logger.warning(f"拉取{kind}离线消息失败: {e}")
        return 0


async def _close_ws(client: BoxIM) -> None:
    try:
        ws = client._ws
        if ws is None:
            return
        ws._running = False
        task = getattr(ws, "_task", None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        if ws._ws is not None:
            try:
                await asyncio.wait_for(ws._ws.close(), timeout=3)
            except (asyncio.TimeoutError, Exception):
                pass
            ws._ws = None
    except Exception as e:
        logger.debug(f"关闭 WebSocket 失败: {e}")


async def _close_http(client: BoxIM) -> None:
    try:
        http = client._http
        if http is None:
            return
        if http._async_session is not None:
            session = http._async_session
            if not session.closed:
                await asyncio.wait_for(session.close(), timeout=3)
            http._async_session = None
        if http._session is not None:
            http._session.close()
            http._session = None
    except asyncio.TimeoutError:
        logger.debug("关闭 aiohttp session 超时")
    except Exception as e:
        logger.debug(f"关闭 aiohttp session 失败: {e}")


async def _close_stray_sessions() -> None:
    try:
        import aiohttp
        import gc as _gc

        for obj in _gc.get_objects():
            if isinstance(obj, aiohttp.ClientSession) and not obj.closed:
                try:
                    await asyncio.wait_for(obj.close(), timeout=2)
                except Exception:
                    pass
    except Exception:
        pass


async def _cancel_tasks() -> None:
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if not tasks:
        return
    logger.debug(f"正在取消 {len(tasks)} 个任务")
    for task in tasks:
        if not task.done():
            task.cancel()
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=5
        )
        for i, result in enumerate(results):
            if isinstance(result, Exception) and not isinstance(
                result, asyncio.CancelledError
            ):
                logger.debug(f"任务 {i+1} 清理异常: {type(result).__name__}: {result}")
    except asyncio.TimeoutError:
        logger.debug("任务清理超时")
    except Exception as e:
        logger.debug(f"任务清理失败: {e}")


async def graceful_shutdown(silent: bool = False) -> None:
    """优雅关闭适配器。"""
    global boxim_client
    try:
        logger.info("正在关闭适配器...") if not silent else logger.debug("清理资源中...")
        try:
            message_handler.save_offline_state()
        except Exception as e:
            logger.debug(f"保存离线状态失败: {e}")
        from src.config import config_manager

        try:
            await config_manager.stop_watch()
        except Exception as e:
            logger.debug(f"停止配置监控失败: {e}")
        try:
            await asyncio.wait_for(mmc_stop_com(), timeout=5)
        except asyncio.TimeoutError:
            logger.debug("关闭 MMC 连接超时")
        except Exception as e:
            logger.debug(f"关闭 MMC 连接失败: {e}")
        if boxim_client:
            await _close_ws(boxim_client)
            await _close_http(boxim_client)
            await _close_stray_sessions()
            logger.debug("BoxIM 连接已关闭")
            boxim_client = None
        await _cancel_tasks()
        logger.info("适配器已成功关闭") if not silent else logger.debug("资源清理完成")
    except Exception as e:
        logger.debug(f"graceful_shutdown 异常: {e}", exc_info=True)
