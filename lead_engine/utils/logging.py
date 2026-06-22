"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Optional


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or "baess_lead_engine")
