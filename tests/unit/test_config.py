"""
Unit tests for Configuration Manager and environment variable resolution.
"""
import os
import tempfile
from pathlib import Path
import pytest

from backend.core.config import ConfigManager, DEFAULT_CONFIG, DEFAULT_VETO, _deep_merge


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    override = {"b": {"d": 4, "e": 5}, "f": 6}
    merged = _deep_merge(base, override)
    assert merged["a"] == 1
    assert merged["b"]["c"] == 2
    assert merged["b"]["d"] == 4
    assert merged["b"]["e"] == 5
    assert merged["f"] == 6


def test_config_load_defaults():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "config.json"
        cfg = ConfigManager(config_path=tmp_path)
        data = cfg.load()
        assert data["profile"]["role_focus"] == "backend"
        assert "Node.js" in data["profile"]["tech_stack"]
        assert data["ai"]["score_threshold"] == 50


def test_config_save_and_reload():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "config.json"
        cfg = ConfigManager(config_path=tmp_path)
        custom = cfg.load()
        custom["profile"]["experience_years"] = 5
        custom["ai"]["score_threshold"] = 75
        cfg.save(custom)

        reloaded = cfg.reload()
        assert reloaded["profile"]["experience_years"] == 5
        assert reloaded["ai"]["score_threshold"] == 75


def test_veto_load_defaults():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_veto = Path(tmp_dir) / "veto.json"
        cfg = ConfigManager(veto_path=tmp_veto)
        veto_data = cfg.load_veto()
        assert "walk-in" in veto_data["titles"]
        assert "infosys" in veto_data["companies"]


def test_naukri_credentials_resolution(monkeypatch):
    monkeypatch.setenv("NAUKRI_USERNAME", "test_user@example.com")
    monkeypatch.setenv("PASSWORD", "secret123")
    cfg = ConfigManager()
    user, pwd = cfg.get_naukri_credentials()
    assert user == "test_user@example.com"
    assert pwd == "secret123"


def test_naukri_credentials_windows_collision_fallback(monkeypatch):
    # If NAUKRI_USERNAME is not set and USERNAME contains no '@', fallback avoids OS username
    monkeypatch.delenv("NAUKRI_USERNAME", raising=False)
    monkeypatch.setenv("USERNAME", "WINDOWS_USER")
    monkeypatch.setenv("PASSWORD", "pwd")
    cfg = ConfigManager()
    user, _ = cfg.get_naukri_credentials()
    # Should not take WINDOWS_USER if on Windows and no '@'
    if os.name == "nt":
        assert user == ""
