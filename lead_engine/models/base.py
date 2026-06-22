"""SQLAlchemy declarative base."""

from __future__ import annotations

import enum
from typing import Any, Optional, Type

from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.types import TypeDecorator


class Base(DeclarativeBase):
    pass


class StrEnumColumn(TypeDecorator):
    """Store enum values in VARCHAR; accept legacy name or value on read."""

    impl = String
    cache_ok = True

    def __init__(self, enum_cls: Type[enum.Enum], length: int = 50) -> None:
        self.enum_cls = enum_cls
        super().__init__(length)

    def process_bind_param(
        self, value: Optional[Any], dialect: Any
    ) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return value.value
        return str(value)

    def process_result_value(
        self, value: Optional[str], dialect: Any
    ) -> Optional[enum.Enum]:
        if value is None:
            return None
        try:
            return self.enum_cls(value)
        except ValueError:
            pass
        try:
            return self.enum_cls[value]
        except KeyError as exc:
            raise LookupError(
                f"'{value}' is not a valid {self.enum_cls.__name__}"
            ) from exc


def str_enum_column(enum_cls: Type[enum.Enum], **kwargs: Any):
    """Create a mapped column for a string-backed enum."""
    length = kwargs.pop("length", 50)
    return mapped_column(StrEnumColumn(enum_cls, length=length), **kwargs)
