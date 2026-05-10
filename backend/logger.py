import json
import logging
import logging.handlers
import os


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }, ensure_ascii=False)


def setup_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    if not any(isinstance(h, logging.StreamHandler)
               and not isinstance(h, logging.FileHandler)
               and type(h).__module__ in ("logging", __name__)
               for h in root.handlers):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)-20s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(console)

    log_file = os.environ.get("LOG_FILE", "logs/app.json")
    if log_file:
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else "logs", exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(JsonFormatter())
        root.addHandler(file_handler)
