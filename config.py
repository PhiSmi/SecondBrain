"""Config loader — reads config.yaml and provides typed access."""

from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_config: dict | None = None
_config_mtime: float | None = None


def _load() -> dict:
    global _config, _config_mtime
    mtime = _CONFIG_PATH.stat().st_mtime
    if _config is None or _config_mtime != mtime:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
        _config_mtime = mtime
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


def ingestion() -> dict:
    return _load().get("ingestion", {})


def workspaces() -> dict:
    return _load().get("workspaces", {})


def recrawl() -> dict:
    return _load().get("recrawl", {})


def default_embedding_model() -> str:
    embedding_models = models("embedding")
    default = next((m["id"] for m in embedding_models if m.get("default")), None)
    if default:
        return default
    if embedding_models:
        return embedding_models[0]["id"]
    return "all-MiniLM-L6-v2"
