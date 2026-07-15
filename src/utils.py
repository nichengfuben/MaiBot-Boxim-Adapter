import base64
import io
import asyncio
import urllib3
import ssl

from PIL import Image
from typing import Union, Optional

from .logger import logger


class SSLAdapter(urllib3.PoolManager):
    def __init__(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT@SECLEVEL=1")
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs["ssl_context"] = context
        super().__init__(*args, **kwargs)


def _blocking_download(url: str, timeout: int = 30) -> bytes:
    http = SSLAdapter()
    response = http.request("GET", url, timeout=timeout)
    if response.status != 200:
        raise Exception(f"HTTP Error: {response.status}")
    return response.data


async def download_url(url: str, timeout: int = 30) -> bytes:
    """下载 URL 内容"""
    logger.debug(f"下载: {url}")
    try:
        data = await asyncio.to_thread(_blocking_download, url, timeout)
        return data
    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        raise


async def get_image_base64(url: str) -> str:
    """获取图片的 Base64"""
    image_bytes = await download_url(url)
    return base64.b64encode(image_bytes).decode("utf-8")


def convert_image_to_gif(image_base64: str) -> str:
    """将 Base64 编码的图片转换为 GIF 格式"""
    logger.debug("转换图片为 GIF 格式")
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes))
        output_buffer = io.BytesIO()
        image.save(output_buffer, format="GIF")
        output_buffer.seek(0)
        return base64.b64encode(output_buffer.read()).decode("utf-8")
    except Exception as e:
        logger.error(f"图片转换为 GIF 失败: {str(e)}")
        return image_base64


def get_image_format(raw_data: str) -> str:
    """从 Base64 编码的数据中确定图片的格式"""
    image_bytes = base64.b64decode(raw_data)
    fmt = Image.open(io.BytesIO(image_bytes)).format
    return fmt.lower() if fmt else "png"
