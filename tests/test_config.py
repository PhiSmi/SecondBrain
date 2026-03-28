"""Tests for the config loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config


class TestConfigLoader:
    def test_branding_loaded(self):
        brand = config.branding()
        assert "app_name" in brand
        assert brand["app_name"] == "SecondBrain"

    def test_theme_loaded(self):
        theme = config.theme()
        assert "primary_color" in theme
        assert theme["primary_color"].startswith("#")

    def test_models_llm(self):
        llms = config.models("llm")
        assert len(llms) >= 1
        assert any(m.get("default") for m in llms)

    def test_models_embedding(self):
        embeds = config.models("embedding")
        assert len(embeds) >= 1
        assert any("MiniLM" in m["name"] for m in embeds)

    def test_retrieval_defaults(self):
        ret = config.retrieval()
        assert ret["chunk_size"] == 500
        assert ret["top_k"] == 10
        assert ret["final_k"] == 5

    def test_workspaces(self):
        ws = config.workspaces()
        assert ws["default"] == "default"
        assert len(ws["predefined"]) >= 1

    def test_ui_section(self):
        ask_ui = config.ui("ask")
        assert "heading" in ask_ui
        assert "question_placeholder" in ask_ui

    def test_get_helper(self):
        assert config.get("branding", "app_name") == "SecondBrain"
        assert config.get("nonexistent", "key", "fallback") == "fallback"
