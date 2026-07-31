from maim_message import Seg, MessageBase
from typing import List, Dict

from src.runtime.logger import logger
from src.config import global_config
from src.runtime.utils import get_image_format, convert_image_to_gif


class SendMessageHandleClass:
    @classmethod
    def parse_seg_to_boxim_format(cls, message_segment: Seg):
        """Parse Seg into BoxIM sending format"""
        parsed_payload: List = cls.process_seg_recursive(message_segment)
        return parsed_payload

    @classmethod
    def process_seg_recursive(cls, seg_data: Seg, in_forward: bool = False) -> List:
        payload: List = []
        if seg_data.type == "seglist":
            if not seg_data.data:
                return []
            for seg in seg_data.data:
                payload = cls.process_message_by_type(seg, payload, in_forward)
        else:
            payload = cls.process_message_by_type(seg_data, payload, in_forward)
        return payload

    @classmethod
    def process_message_by_type(cls, seg: Seg, payload: List, in_forward: bool = False) -> List:
        handlers = {
            "reply": (cls.handle_reply_message, True),
            "text": (cls.handle_text_message, False),
            "at": (cls.handle_at_message, False),
            "face": (cls.handle_native_face_message, False),
            "image": (cls.handle_image_message, False),
            "emoji": (cls.handle_emoji_message, False),
            "voice": (cls.handle_voice_message, False),
            "voiceurl": (cls.handle_voiceurl_message, False),
            "music": (cls.handle_music_message, False),
            "videourl": (cls.handle_videourl_message, False),
            "file": (cls.handle_file_message, False),
            "imageurl": (cls.handle_imageurl_message, False),
            "video": (cls.handle_video_message, False),
        }
        if seg.type == "reply" and seg.data == "notice":
            return payload
        if seg.type == "text" and not seg.data:
            return payload
        if seg.type == "forward" and not in_forward:
            return [cls.handle_forward_message(MessageBase.from_dict(i)) for i in seg.data]
        entry = handlers.get(seg.type)
        if not entry:
            return payload
        handler, prepend = entry
        return cls.build_payload(payload, handler(seg.data), prepend)

    @classmethod
    def handle_forward_message(cls, item: MessageBase) -> Dict:
        message_segment: Seg = item.message_segment
        if message_segment.type == "id":
            return {"type": "node", "data": {"id": message_segment.data}}
        else:
            user_info = None
            if item.message_info.receiver_info:
                user_info = item.message_info.receiver_info.user_info
            if not user_info and item.message_info.user_info:
                user_info = item.message_info.user_info
            if not user_info and item.message_info.sender_info:
                user_info = item.message_info.sender_info.user_info
            content = cls.process_seg_recursive(message_segment, True)
            return {
                "type": "node",
                "data": {
                    "name": user_info.user_nickname or "User" if user_info else "User",
                    "uin": user_info.user_id if user_info else "0",
                    "content": content,
                },
            }

    @staticmethod
    def build_payload(payload: List, addon: dict, is_reply: bool = False) -> List:
        if is_reply:
            temp_list = []
            temp_list.append(addon)
            for i in payload:
                if i.get("type") == "reply":
                    logger.debug("Multiple replies detected, using latest")
                    continue
                temp_list.append(i)
            return temp_list
        else:
            payload.append(addon)
            return payload

    @staticmethod
    def handle_reply_message(id: str) -> dict:
        return {"type": "reply", "data": {"id": id}}

    @staticmethod
    def handle_at_message(at_data) -> dict:
        user_id = at_data.get("user_id") if isinstance(at_data, dict) else at_data
        return {"type": "at", "data": {"user_id": user_id}}

    @staticmethod
    def handle_text_message(message: str) -> dict:
        return {"type": "text", "data": {"text": message}}

    @staticmethod
    def handle_native_face_message(face_id: int) -> dict:
        return {"type": "face", "data": {"id": int(face_id)}}

    @staticmethod
    def handle_image_message(encoded_image: str) -> dict:
        return {
            "type": "image",
            "data": {
                "file": f"base64://{encoded_image}",
                "subtype": 0,
            },
        }

    @staticmethod
    def handle_emoji_message(encoded_emoji: str) -> dict:
        encoded_image = encoded_emoji
        image_format = get_image_format(encoded_emoji)
        if image_format != "gif":
            encoded_image = convert_image_to_gif(encoded_emoji)
        return {
            "type": "image",
            "data": {
                "file": f"base64://{encoded_image}",
                "subtype": 1,
                "summary": "[Animated Emoji]",
            },
        }

    @staticmethod
    def handle_voice_message(encoded_voice: str) -> dict:
        if not global_config.voice.use_tts:
            logger.warning("Voice message processing not enabled")
            return {}
        if not encoded_voice:
            return {}
        return {
            "type": "voice",
            "data": {"file": f"base64://{encoded_voice}"},
        }

    @staticmethod
    def handle_voiceurl_message(voice_url: str) -> dict:
        return {
            "type": "voice",
            "data": {"file": voice_url},
        }

    @staticmethod
    def handle_music_message(music_data) -> dict:
        if isinstance(music_data, str):
            return {
                "type": "music",
                "data": {"type": "163", "id": music_data},
            }

        if isinstance(music_data, dict):
            platform = music_data.get("type", "163")
            song_id = music_data.get("id", "")

            if platform not in ["163", "qq"]:
                logger.warning(f"Unsupported music platform: {platform}, using default 163")
                platform = "163"

            if not isinstance(song_id, str):
                song_id = str(song_id)

            return {
                "type": "music",
                "data": {"type": platform, "id": song_id},
            }

        logger.error(f"Unsupported music data format: {type(music_data)}")
        return {}

    @staticmethod
    def handle_videourl_message(video_url: str) -> dict:
        return {
            "type": "video",
            "data": {"file": video_url},
        }

    @staticmethod
    def handle_file_message(file_data) -> dict:
        if isinstance(file_data, str):
            return {
                "type": "file",
                "data": {"file": f"file://{file_data}"},
            }

        if isinstance(file_data, dict):
            data = {}

            if "file" in file_data:
                file_value = file_data["file"]
                if not any(file_value.startswith(prefix) for prefix in ["file://", "http://", "https://", "base64://"]):
                    data["file"] = f"file://{file_value}"
                else:
                    data["file"] = file_value
            else:
                if "path" in file_data:
                    data["file"] = f"file://{file_data['path']}"
                elif "url" in file_data:
                    data["file"] = file_data["url"]
                else:
                    logger.warning("File message missing file/path/url field")
                    return {}

            if "name" in file_data:
                data["name"] = file_data["name"]
            if "thumb" in file_data:
                data["thumb"] = file_data["thumb"]

            return {
                "type": "file",
                "data": data,
            }

        logger.warning(f"Unsupported file data type: {type(file_data)}")
        return {}

    @staticmethod
    def handle_imageurl_message(image_url: str) -> dict:
        return {
            "type": "image",
            "data": {"file": image_url},
        }

    @staticmethod
    def handle_video_message(encoded_video: str) -> dict:
        if not encoded_video:
            logger.error("Video data is empty")
            return {}

        logger.info(f"Processing video message, data length: {len(encoded_video)} chars")

        return {
            "type": "video",
            "data": {"file": f"base64://{encoded_video}"},
        }
