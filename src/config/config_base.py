from dataclasses import dataclass, fields, MISSING
from typing import TypeVar, Type, Any, get_origin, get_args, Literal, Dict, Union

T = TypeVar("T", bound="ConfigBase")

TOML_DICT_TYPE = {int, float, str, bool, list, dict}


@dataclass
class ConfigBase:
    """配置类的基类"""

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从字典加载配置字段"""
        if not isinstance(data, dict):
            raise TypeError(f"Expected a dictionary, got {type(data).__name__}")
        init_args: Dict[str, Any] = {}
        for f in fields(cls):
            field_name = f.name
            if field_name.startswith("_"):
                continue
            if field_name not in data:
                if f.default is not MISSING or f.default_factory is not MISSING:
                    continue
                raise ValueError(f"Missing required field: '{field_name}'")
            try:
                init_args[field_name] = cls._convert_field(data[field_name], f.type)
            except TypeError as e:
                raise TypeError(f"字段 '{field_name}' 出现类型错误: {e}") from e
            except Exception as e:
                raise RuntimeError(
                    f"无法将字段 '{field_name}' 转换为目标类型，出现错误: {e}"
                ) from e
        return cls(**init_args)

    @classmethod
    def _convert_field(cls, value: Any, field_type: Type[Any]) -> Any:
        """转换字段值为指定类型。"""
        if isinstance(field_type, type) and issubclass(field_type, ConfigBase):
            return field_type.from_dict(value)
        origin = get_origin(field_type)
        args = get_args(field_type)
        if origin in {list, set, tuple}:
            return cls._convert_sequence(value, field_type, origin, args)
        if origin is dict:
            return cls._convert_mapping(value, field_type, args)
        if origin is Union:
            return cls._convert_union(value, field_type, args)
        if origin is None:
            return cls._convert_plain(value, field_type)
        if origin is Literal:
            return cls._convert_literal(value, field_type)
        if field_type is Any:
            return value
        try:
            return field_type(value)
        except (ValueError, TypeError) as e:
            raise TypeError(
                f"无法将 {type(value).__name__} 转换为 {field_type.__name__}"
            ) from e

    @classmethod
    def _convert_sequence(cls, value, field_type, origin, args):
        if not isinstance(value, list):
            raise TypeError(
                f"Expected an list for {field_type.__name__}, got {type(value).__name__}"
            )
        if origin is list:
            return [cls._convert_field(item, args[0]) for item in value]
        if origin is set:
            return {cls._convert_field(item, args[0]) for item in value}
        if len(value) != len(args):
            raise TypeError(
                f"Expected {len(args)} items for {field_type.__name__}, got {len(value)}"
            )
        return tuple(cls._convert_field(item, arg) for item, arg in zip(value, args))

    @classmethod
    def _convert_mapping(cls, value, field_type, args):
        if not isinstance(value, dict):
            raise TypeError(
                f"Expected a dictionary for {field_type.__name__}, got {type(value).__name__}"
            )
        if len(args) != 2:
            raise TypeError(
                f"Expected a dictionary with two type arguments for {field_type.__name__}"
            )
        key_type, value_type = args
        return {
            cls._convert_field(k, key_type): cls._convert_field(v, value_type)
            for k, v in value.items()
        }

    @classmethod
    def _convert_union(cls, value, field_type, args):
        if value is None:
            return None
        if type(value) not in args:
            raise TypeError(
                f"Expected {args} for {field_type.__name__}, got {type(value).__name__}"
            )
        return cls._convert_field(value, args[0])

    @classmethod
    def _convert_plain(cls, value, field_type):
        if isinstance(value, field_type):
            return field_type(value)
        raise TypeError(f"Expected {field_type.__name__}, got {type(value).__name__}")

    @classmethod
    def _convert_literal(cls, value, field_type):
        allowed = get_args(field_type)
        if value in allowed:
            return value
        raise TypeError(
            f"Value '{value}' is not in allowed values {allowed} for Literal type"
        )

    def __str__(self):
        items = ", ".join(f"{f.name}={getattr(self, f.name)}" for f in fields(self))
        return f"{self.__class__.__name__}({items})"
