from __future__ import annotations
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

WHITELIST_FILE = DATA_DIR / "whitelist.json"
DEFAULT_WHITELIST_DATA: list[int] = []

def _read_json(path: Path, default: any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _write_json(path: Path, data: any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_whitelist() -> list[int]:
    return _read_json(WHITELIST_FILE, DEFAULT_WHITELIST_DATA)

def add_whitelisted_role(role_id: int):
    data = get_whitelist()
    if role_id not in data:
        data.append(role_id)
        _write_json(WHITELIST_FILE, data)

def remove_whitelisted_role(role_id: int):
    data = get_whitelist()
    if role_id in data:
        data.remove(role_id)
        _write_json(WHITELIST_FILE, data)
