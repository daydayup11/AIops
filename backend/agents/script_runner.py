import base64
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from models.schemas import PyScript
from config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 60
_cfg = settings["clickhouse"]


def run_script_runner(
    py_script: PyScript,
    timeout: int = _DEFAULT_TIMEOUT,
) -> list:
    with tempfile.TemporaryDirectory(prefix="aiops_renders_") as output_dir:
        env = os.environ.copy()
        env.update({
            "CH_HOST": str(_cfg["host"]),
            "CH_PORT": str(_cfg["port"]),
            "CH_USER": str(_cfg["user"]),
            "CH_PASSWORD": str(_cfg["password"]),
            "CH_DATABASE": str(_cfg["database"]),
            "OUTPUT_DIR": output_dir,
            "MPLBACKEND": "Agg",
        })

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
            f.write(py_script.script_code)
            script_path = f.name

        try:
            logger.info("script_runner: executing script  len=%d  timeout=%ds",
                        len(py_script.script_code), timeout)
            t0 = time.perf_counter()
            proc = subprocess.run(
                [sys.executable, script_path],
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            elapsed = time.perf_counter() - t0
            logger.info("script_runner: done  %.2fs  returncode=%d", elapsed, proc.returncode)
            if proc.stdout:
                logger.debug("script_runner: stdout\n%s", proc.stdout[-1000:])
            if proc.stderr:
                logger.info("script_runner: stderr\n%s", proc.stderr[-1000:])

            if proc.returncode != 0:
                err = proc.stderr[-500:] if proc.stderr else "脚本执行失败"
                logger.warning("script_runner: script failed\n%s", proc.stderr)
                return [{"render": "text", "content": f"⚠️ 脚本执行错误：{err}"}]

            all_files = list(Path(output_dir).iterdir())
            logger.info("script_runner: output_dir contents: %s", [f.name for f in all_files])
            png_files = sorted(Path(output_dir).glob("*.png"))
            logger.info("script_runner: found %d PNG files", len(png_files))

            if not png_files:
                stdout_hint = proc.stdout[-300:] if proc.stdout else ""
                stderr_hint = proc.stderr[-300:] if proc.stderr else ""
                detail = f"stdout: {stdout_hint}\nstderr: {stderr_hint}".strip()
                return [{"render": "text", "content": f"⚠️ 脚本执行完成但未生成图表，请重试\n{detail}"}]

            outputs = []
            for png_path in png_files:
                data = png_path.read_bytes()
                b64 = base64.b64encode(data).decode("ascii")
                outputs.append({"render": "image", "content": b64})

            json_path = Path(output_dir) / "data_summary.json"
            if json_path.exists():
                try:
                    json_content = json_path.read_text(encoding="utf-8")
                    outputs.append({"render": "json", "content": json_content})
                    logger.info("script_runner: data_summary.json found (%d bytes)", len(json_content))
                except Exception as exc:
                    logger.warning("script_runner: failed to read data_summary.json: %s", exc)

            return outputs

        except subprocess.TimeoutExpired:
            logger.warning("script_runner: timeout after %ds", timeout)
            return [{"render": "text", "content": f"⚠️ 脚本执行超时（>{timeout}秒），请简化查询后重试"}]
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
