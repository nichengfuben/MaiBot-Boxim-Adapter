from __future__ import annotations

from typing import Optional

from src.send_handler.im_api.notify import send_business_error


class ImCoreMixin:
    def __init__(self):
        self.boxim_client = None

    def set_boxim_client(self, client):
        """设置 BoxIM SDK 实例"""
        self.boxim_client = client

    async def _notify_business_error(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
        error_type: str,
        error_message: str,
        error_code: Optional[int] = None,
    ) -> None:
        """向 Bot 发送业务错误通知。"""
        await send_business_error(user_id, group_id, error_type, error_message, error_code)
