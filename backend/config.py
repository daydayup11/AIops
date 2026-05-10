import yaml
import os

_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")

with open(_config_path, "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)
