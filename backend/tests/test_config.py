import pytest
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_settings_loads_clickhouse():
    from config import settings
    assert settings["clickhouse"]["host"] == "10.161.111.100"
    assert settings["clickhouse"]["port"] == 9000

def test_settings_loads_llm():
    from config import settings
    assert "base_url" in settings["llm"]
    assert "model" in settings["llm"]

def test_settings_loads_executor():
    from config import settings
    assert settings["executor"]["max_workers"] == 5
