"""
Configuration persistence module.
Stores kubeconfig path and API base URL in ~/.config/k8s-log-analyzer/settings.json
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Settings:
    kubeconfig_path: Optional[str] = None
    api_base_url: Optional[str] = None


def _config_dir() -> Path:
    d = Path.home() / ".config" / "k8s-log-analyzer"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return _config_dir() / "settings.json"


def load_settings() -> Settings:
    """Load settings from JSON file. Returns default Settings if file doesn't exist or is invalid."""
    path = _settings_path()
    if not path.exists():
        return Settings()
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings(
            kubeconfig_path=data.get("kubeconfig_path"),
            api_base_url=data.get("api_base_url"),
        )
    except (json.JSONDecodeError, IOError):
        return Settings()


def save_settings(settings: Settings) -> None:
    """Save settings to JSON file."""
    path = _settings_path()
    data = {}
    if settings.kubeconfig_path:
        data["kubeconfig_path"] = settings.kubeconfig_path
    if settings.api_base_url:
        data["api_base_url"] = settings.api_base_url
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
