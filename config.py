"""Config loader — reads config.yaml and provides typed access."""

from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_config: dict | None = None


def _load() -> dict:
    global _config
    if _config is None:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def get(section: str, key: str | None = None, default=None):
    """Get a config value.  e.g. get("branding", "app_name") or get("theme")."""
    cfg = _load()
    val = cfg.get(section, {})
    if key is None:
        return val if val else default
    if isinstance(val, dict):
        return val.get(key, default)
    return default


def branding() -> dict:
    return _load().get("branding", {})


def ui(section: str | None = None) -> dict:
    ui_cfg = _load().get("ui", {})
    if section:
        return ui_cfg.get(section, {})
    return ui_cfg


def theme() -> dict:
    return _load().get("theme", {})


def models(kind: str = "llm") -> list[dict]:
    return _load().get("models", {}).get(kind, [])


def retrieval() -> dict:
    return _load().get("retrieval", {})


def workspaces() -> dict:
    return _load().get("workspaces", {})


def recrawl() -> dict:
    return _load().get("recrawl", {})
