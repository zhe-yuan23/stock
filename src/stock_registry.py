"""Shared stock watchlist helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path


STOCK_ID_RE = re.compile(r"^\d{4}$")


def normalize_stock_id(stock_id: str) -> str:
    value = str(stock_id).strip()
    if not STOCK_ID_RE.fullmatch(value):
        raise ValueError("股票代號必須是 4 位數字")
    return value


def load_stock_ids(data_dir: Path) -> list[str]:
    watchlist_path = data_dir / "watchlist.json"
    if watchlist_path.exists():
        try:
            payload = json.loads(watchlist_path.read_text(encoding="utf-8-sig"))
            values = payload.get("stocks", [])
            ids = sorted({normalize_stock_id(value) for value in values}, key=int)
            if ids:
                return ids
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    return sorted(
        {
            normalize_stock_id(path.name)
            for path in data_dir.iterdir()
            if path.is_dir() and path.name not in {"manual_data", "taiex"} and STOCK_ID_RE.fullmatch(path.name)
        },
        key=int,
    ) if data_dir.exists() else []


def update_watchlist(data_dir: Path, stock_id: str) -> list[str]:
    stock_id = normalize_stock_id(stock_id)
    ids = load_stock_ids(data_dir)
    if stock_id not in ids:
        ids.append(stock_id)
    return sorted(set(ids), key=int)
