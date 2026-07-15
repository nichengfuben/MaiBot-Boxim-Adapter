import asyncio
import signal
import sys
import json
from sdk import BoxIM
from src.logger import logger, _unify_external_loggers
from src.recv_handler.message_handler import message_handler
from src.recv_handler.meta_event_handler import meta_event_handler
from src.recv_handler.notice_handler import notice_handler
from src.recv_handler.message_sending import message_send_instance
from src.send_handler.im_sending import boxim_message_sender
from src.config import global_config
from src.mmc_com_layer import mmc_start_com, mmc_stop_com, router
from src.response_pool import put_response, check_timeout_response

message_queue = asyncio.Queue()
boxim_client: BoxIM = None
mmc_ready = asyncio.Event()  # MMC 连接就绪信号


async def boxim_message_handler(msg_data, is_group):
    """Handle messages received from BoxIM WebSocket"""
    try:
        # BoxIM SDK uses camelCase: id, type, content, sendId, recvId, groupId, sendNickName
        message_id = msg_data.get("id")
        msg_type = msg_data.get("type", 0)

        if message_id is None:
            # 某些特殊类型消息没有 id（在线状态、已读回执、系统通知等）
            NO_ID_TYPES = {11, 12, 53, 54, 82} | set(range(100, 111)) | set(range(200, 213))
            if msg_type in NO_ID_TYPES:
                # 通知/系统消息转发到 notice_handler 处理
                msg_data["post_type"] = "notice"
                msg_data["notice_type"] = "notify"
                await notice_handler.handle_notice(msg_data)
                return
            logger.warning(f"BoxIM 消息缺少 id, type={msg_type}, keys={list(msg_data.keys())}, data={json.dumps(msg_data, ensure_ascii=False)}")
            return

        # Pass original BoxIM msg_data to handler, let it do the conversion
        await message_handler.handle_boxim_message(msg_data, is_group)

    except Exception as e:
        logger.error(f"Error handling BoxIM message: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def message_process():
    """Process messages from the queue"""
    # 等待 MMC 连接就绪后再开始消费消息
    await mmc_ready.wait()
    while True:
        message = await message_queue.get()
        post_type = message.get("post_type")
        if post_type == "message":
            await message_handler.handle_boxim_message(message, message.get("is_group", False))
        elif post_type == "meta_event":
            await meta_event_handler.handle_meta_event(message)
        elif post_type == "notice":
            await notice_handler.handle_notice(message)
        else:
            logger.warning(f"Unknown post_type: {post_type}")
        message_queue.task_done()


async def version_watch() -> None:
    """定期检查模板版本，检测到新版本时自动更新配置并重启。"""
    from src.config.config import get_template_version, get_current_config_version, update_config

    check_interval = 60
    while True:
        await asyncio.sleep(check_interval)
        try:
            template_ver = get_template_version()
            current_ver = get_current_config_version()
            if template_ver and current_ver and template_ver != current_ver:
                logger.info(f"检测到新版本: v{current_ver} -> v{template_ver}，准备自动更新...")
                await graceful_shutdown(silent=False)
                update_config()
        except Exception as e:
            logger.debug(f"版本检查异常: {e}")


async def init_boxim():
    """Initialize BoxIM SDK and connect"""
    global boxim_client

    config = global_config.boxim
    logger.info(f"Initializing BoxIM SDK: {config.base_url}")

    boxim_client = BoxIM(
        base_url=config.base_url,
        ws_url=config.ws_url,
        auto_refresh_token=True,
        debug=global_config.debug.level == "DEBUG",
    )

    # BoxIM SDK 在初始化时可能给自己的 logger 添加了独立的 handler，
    # 清除所有第三方库 logger 的 handler，让日志统一走 echotools 格式。
    _unify_external_loggers()

    # Login
    await boxim_client.alogin(config.username, config.password)
    logger.info(f"BoxIM login successful: {config.username}")

    # 获取 bot 自身信息并设置
    try:
        self_info = await boxim_client.aget_me()
        bot_user_id = self_info.get("id", 0)
        bot_nickname = self_info.get("nickName") or self_info.get("userName") or config.username
        message_handler.set_bot_info(bot_user_id, bot_nickname)
        logger.info(f"Bot 自身信息: user_id={bot_user_id}, nickname={bot_nickname!r}")
    except Exception as e:
        logger.warning(f"获取 bot 自身信息失败，使用登录用户名作为昵称: {e}")
        message_handler.set_bot_info(0, config.username)

    # Set up the boxim client reference for sending
    boxim_message_sender.set_boxim_client(boxim_client)
    
    # Set boxim client on message_handler for user info lookup
    message_handler.set_boxim_client(boxim_client)

    # Register message handlers
    boxim_client.on_message(boxim_message_handler)

    # Start WebSocket listening in background task
    asyncio.create_task(boxim_client.start_listening())
    logger.info("BoxIM WebSocket listener started")

    # 离线状态持久化：从文件恢复上次记录的最大消息 ID
    import os, json as _json
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "offline_state.json")
    os.makedirs(os.path.dirname(state_file), exist_ok=True)

    last_private_id = 0
    last_group_id = 0
    try:
        if os.path.exists(state_file):
            with open(state_file, "r") as f:
                state = _json.load(f)
                last_private_id = state.get("last_private_id", 0)
                last_group_id = state.get("last_group_id", 0)
            logger.info(f"离线状态恢复: private_id={last_private_id}, group_id={last_group_id}")
    except Exception as e:
        logger.debug(f"读取离线状态文件失败，从头开始: {e}")

    # 将状态追踪委托给 message_handler（实时 + 离线消息均会更新 max ID）
    message_handler.init_offline_state(state_file, last_private_id, last_group_id)

    # 拉取离线消息，放入队列等 MMC 就绪后处理
    try:
        offline_count = 0

        # 私聊离线消息
        try:
            private_msgs = await boxim_client.aload_private_offline_message(last_private_id)
            if private_msgs:
                for msg in private_msgs:
                    msg["post_type"] = "message"
                    msg["is_group"] = False
                    await message_queue.put(msg)
                    offline_count += 1
        except Exception as e:
            logger.warning(f"拉取私聊离线消息失败: {e}")

        # 群聊离线消息
        try:
            group_msgs = await boxim_client.aload_group_offline_message(last_group_id)
            if group_msgs:
                for msg in group_msgs:
                    msg["post_type"] = "message"
                    msg["is_group"] = True
                    await message_queue.put(msg)
                    offline_count += 1
        except Exception as e:
            logger.warning(f"拉取群聊离线消息失败: {e}")

        if offline_count > 0:
            logger.info(f"已将 {offline_count} 条离线消息放入队列 (private>{last_private_id}, group>{last_group_id})")
    except Exception as e:
        logger.warning(f"离线消息拉取失败: {e}")

    return boxim_client


# 用于信号触发的关闭事件
_shutdown_event: asyncio.Event | None = None


def _install_signal_handlers(loop: asyncio.AbstractEventLoop) -> None:
    """注册 SIGTERM / SIGINT 信号处理器，触发优雅关闭。"""
    global _shutdown_event
    _shutdown_event = asyncio.Event()

    def _signal_handler():
        logger.warning("收到退出信号，正在优雅关闭...")
        if _shutdown_event and not _shutdown_event.is_set():
            _shutdown_event.set()

    # Windows 不支持 loop.add_signal_handler，使用 signal.signal 替代
    if sys.platform != "win32":
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _signal_handler)
    else:
        # Windows: signal.signal 只能在主线程调用，这里符合条件
        def _win_handler(signum, frame):
            _signal_handler()
        signal.signal(signal.SIGTERM, _win_handler)
        # 不覆盖 SIGINT：保留 KeyboardInterrupt 作为备选路径


async def _wait_for_shutdown_signal() -> None:
    """等待关闭信号。此任务与核心任务并行运行，信号触发时结束。"""
    if _shutdown_event:
        await _shutdown_event.wait()
    else:
        # 如果没有设置事件，永不返回（依赖 KeyboardInterrupt）
        await asyncio.Event().wait()


async def main():
    # 注册信号处理器
    _install_signal_handlers(asyncio.get_running_loop())

    # Start config file watcher
    from src.config import config_manager
    asyncio.create_task(config_manager.start_watch())

    # Initialize BoxIM（指数退避无限重试，最大间隔 300 秒）
    backoff = 1
    max_backoff = 300
    attempt = 0
    while True:
        attempt += 1
        try:
            await init_boxim()
            break
        except KeyboardInterrupt:
            raise
        except Exception as e:
            logger.error(f"BoxIM 连接失败 (第 {attempt} 次): {e}")
            logger.info(f"{backoff} 秒后重试...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

    # 并行启动核心任务（含版本监控 + 信号等待）
    # 使用 FIRST_COMPLETED：当 _wait_for_shutdown_signal() 完成时立即返回，
    # 其余无限循环任务由 graceful_shutdown() 统一取消。
    _tasks = [
        asyncio.create_task(mmc_start_com()),
        asyncio.create_task(message_process()),
        asyncio.create_task(check_timeout_response()),
        asyncio.create_task(version_watch()),
        asyncio.create_task(_wait_for_shutdown_signal()),
    ]
    done, pending = await asyncio.wait(_tasks, return_when=asyncio.FIRST_COMPLETED)
    # 检查是否有异常退出的任务
    for task in done:
        if task.exception() and not isinstance(task.exception(), asyncio.CancelledError):
            logger.error(f"核心任务异常退出: {task.exception()}")


async def graceful_shutdown(silent: bool = False):
    """优雅关闭适配器。"""
    global boxim_client
    try:
        if not silent:
            logger.info("正在关闭适配器...")
        else:
            logger.debug("清理资源中...")

        # 保存离线消息状态（确保最大消息 ID 持久化）
        try:
            message_handler.save_offline_state()
        except Exception as e:
            logger.debug(f"保存离线状态失败: {e}")

        # 停止配置文件监控
        from src.config import config_manager
        try:
            await config_manager.stop_watch()
        except Exception as e:
            logger.debug(f"停止配置监控失败: {e}")

        # 关闭 MMC 连接（先关 MMC 再关 BoxIM，避免消息丢失）
        try:
            await asyncio.wait_for(mmc_stop_com(), timeout=5)
        except asyncio.TimeoutError:
            logger.debug("关闭 MMC 连接超时")
        except Exception as e:
            logger.debug(f"关闭 MMC 连接失败: {e}")

        # 关闭 BoxIM 连接（包括 WebSocket、aiohttp ClientSession 和 sync Session）
        if boxim_client:
            # 1. 先停止 WebSocket 监听
            try:
                ws = boxim_client._ws
                if ws is not None:
                    ws._running = False
                    if hasattr(ws, '_task') and ws._task and not ws._task.done():
                        ws._task.cancel()
                        try:
                            await ws._task
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

            # 2. 关闭 aiohttp ClientSession
            try:
                http = boxim_client._http
                if http is not None and http._async_session is not None:
                    session = http._async_session
                    if not session.closed:
                        await asyncio.wait_for(session.close(), timeout=3)
                    http._async_session = None
            except asyncio.TimeoutError:
                logger.debug("关闭 aiohttp session 超时")
            except Exception as e:
                logger.debug(f"关闭 aiohttp session 失败: {e}")

            # 3. 关闭同步 requests session
            try:
                http = boxim_client._http
                if http is not None and http._session is not None:
                    http._session.close()
                    http._session = None
            except Exception:
                pass

            # 4. 清理残余的 aiohttp ClientSession 对象
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

            logger.debug("BoxIM 连接已关闭")
            boxim_client = None  # 释放引用，帮助 GC 及时回收

        # 取消所有任务
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if tasks:
            logger.debug(f"正在取消 {len(tasks)} 个任务")
            for task in tasks:
                if not task.done():
                    task.cancel()

        if tasks:
            try:
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=5)
                for i, result in enumerate(results):
                    if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                        logger.debug(f"任务 {i+1} 清理异常: {type(result).__name__}: {result}")
            except asyncio.TimeoutError:
                logger.debug("任务清理超时")
            except Exception as e:
                logger.debug(f"任务清理失败: {e}")

        if not silent:
            logger.info("适配器已成功关闭")
        else:
            logger.debug("资源清理完成")
    except Exception as e:
        logger.debug(f"graceful_shutdown 异常: {e}", exc_info=True)


if __name__ == "__main__":
    import gc
    import warnings

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
        # main() 正常返回意味着收到了关闭信号（_wait_for_shutdown_signal 完成）
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
        logger.debug("详细错误信息:", exc_info=True)
        try:
            loop.run_until_complete(graceful_shutdown(silent=True))
        except Exception as e:
            logger.debug(f"清理资源失败: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            pending = asyncio.all_tasks(loop)
            if pending:
                logger.debug(f"finally 块清理 {len(pending)} 个剩余任务")
                for task in pending:
                    task.cancel()
                try:
                    results = loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    for i, result in enumerate(results):
                        if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                            logger.debug(f"剩余任务 {i+1} 清理异常: {type(result).__name__}: {result}")
                except Exception as e:
                    logger.debug(f"剩余任务清理失败: {e}")
        except Exception as e:
            logger.debug(f"finally 块清理失败: {e}")
        finally:
            # 强制 GC 回收残余协程和 aiohttp session 等对象，
            # 避免 __del__ 在解释器关闭阶段产生 "Unclosed client session"
            # 或 "coroutine was never awaited" 等无害但烦人的警告。
            gc.collect()
            # 抑制关闭阶段残余的各类无害警告
            warnings.filterwarnings("ignore", category=ResourceWarning)
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            warnings.filterwarnings("ignore", message=".*Unclosed client session.*")
            warnings.filterwarnings("ignore", message=".*unclosed.*", category=ResourceWarning)
            warnings.filterwarnings("ignore", message=".*coroutine.*never awaited.*")
            warnings.filterwarnings("ignore", message=".*was never awaited.*")
            # 抑制 asyncio 内部的 SSL/socket 关闭警告
            warnings.filterwarnings("ignore", category=DeprecationWarning)

            if loop and not loop.is_closed():
                logger.debug("关闭事件循环")
                loop.close()
        sys.exit(0)
