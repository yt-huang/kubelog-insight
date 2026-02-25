"""
Persist and query analysis history (local JSON store).
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict


@dataclass
class HistoryEntry:
    timestamp: str
    component_type: str
    component_name: str
    namespace: str
    time_range: Optional[str]
    success: bool
    analysis_text: str
    error_message: str
    preprocessed_preview: str
    id: str = ""


def _history_dir() -> Path:
    d = Path.home() / ".config" / "k8s-log-analyzer" / "history"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_id() -> str:
    t = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    base = _history_dir() / t
    idx = 0
    while (Path(f"{base}-{idx}.json").exists() if idx else (Path(f"{base}.json").exists())):
        idx += 1
    return f"{t}-{idx}" if idx else t


def save_entry(entry: HistoryEntry) -> str:
    if not entry.id:
        entry.id = _next_id()
    path = _history_dir() / f"{entry.id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(entry), f, ensure_ascii=False, indent=2)
    return entry.id


def load_entry(entry_id: str) -> Optional[HistoryEntry]:
    path = _history_dir() / f"{entry_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return HistoryEntry(**data)


def list_entries(limit: int = 100) -> List[HistoryEntry]:
    dir_path = _history_dir()
    files = sorted(dir_path.glob("*.json"), key=os.path.getmtime, reverse=True)
    entries = []
    for p in files[:limit]:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            entries.append(HistoryEntry(**data))
        except Exception:
            continue
    return entries


def delete_entry(entry_id: str) -> bool:
    path = _history_dir() / f"{entry_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False
