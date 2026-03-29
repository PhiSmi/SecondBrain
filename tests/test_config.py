"""Tests for the config loader."""

import tempfile
import time
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

    def test_ingestion_defaults(self):
        ingest_cfg = config.ingestion()
        assert ingest_cfg["max_upload_mb"] == 15
        assert ingest_cfg["max_source_chunks"] == 2000

    def test_workspaces(self):
        ws = config.workspaces()
        assert ws["default"] == "default"
        assert len(ws["predefined"]) >= 1

    def test_jobs_defaults(self):
        jobs_cfg = config.jobs()
        assert jobs_cfg["embedded_worker"] is True
        assert jobs_cfg["lease_seconds"] >= 300

    def test_ui_section(self):
        ask_ui = config.ui("ask")
        assert "heading" in ask_ui
        assert "question_placeholder" in ask_ui

    def test_get_helper(self):
        assert config.get("branding", "app_name") == "SecondBrain"
        assert config.get("nonexistent", "key", "fallback") == "fallback"

    def test_reload_when_config_file_changes(self):
        original_path = config._CONFIG_PATH
        original_config = config._config
        original_mtime = config._config_mtime

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_config = Path(tmpdir) / "config.yaml"
                temp_config.write_text("branding:\n  app_name: First\n", encoding="utf-8")

                config._CONFIG_PATH = temp_config
                config._config = None
                config._config_mtime = None
                assert config.branding()["app_name"] == "First"

                time.sleep(1.1)
                temp_config.write_text("branding:\n  app_name: Second\n", encoding="utf-8")
                assert config.branding()["app_name"] == "Second"
        finally:
            config._CONFIG_PATH = original_path
            config._config = original_config
            config._config_mtime = original_mtime
