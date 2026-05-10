import yaml
import os
import sys

_config_path = os.path.join(os.path.dirname(__file__), "..", "config", "settings.yaml")

try:
    with open(_config_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)
    if settings is None:
        raise ValueError("配置文件为空")
except FileNotFoundError:
    print(f"ERROR: 配置文件不存在: {os.path.abspath(_config_path)}", file=sys.stderr)
    sys.exit(1)
except yaml.YAMLError as e:
    print(f"ERROR: 配置文件 YAML 格式错误: {e}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: 加载配置失败: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)
