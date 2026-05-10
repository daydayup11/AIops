import logging
import re
import threading
import time
import ipaddress
import pandas as pd
from clickhouse_driver import Client
from config import settings

logger = logging.getLogger(__name__)

_cfg = settings["clickhouse"]
_local = threading.local()


def _get_client() -> Client:
    if not hasattr(_local, "client"):
        _local.client = Client(
            host=_cfg["host"],
            port=_cfg["port"],
            user=_cfg["user"],
            password=_cfg["password"],
            database=_cfg["database"],
            connect_timeout=_cfg["connect_timeout"],
        )
    return _local.client

_FORBIDDEN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|RENAME|ATTACH|DETACH)",
    re.IGNORECASE,
)


class SQLSecurityError(Exception):
    pass


def execute_query(sql: str, timeout: int = None) -> pd.DataFrame:
    if _FORBIDDEN.match(sql):
        logger.warning("SQL security block: %s", sql[:60])
        raise SQLSecurityError(f"拒绝执行非SELECT语句: {sql[:60]}")
    t = timeout or _cfg.get("query_timeout", 30)
    logger.debug("Executing SQL: %s", sql[:200])
    start = time.perf_counter()
    try:
        rows, columns = _get_client().execute(
            sql,
            with_column_types=True,
            settings={"max_execution_time": t},
        )
        elapsed = time.perf_counter() - start
        col_names = [c[0] for c in columns]
        df = pd.DataFrame(rows, columns=col_names)
        for col in df.columns:
            if df[col].dtype == object:
                df[col] = df[col].apply(
                    lambda v: str(v) if isinstance(v, (ipaddress.IPv4Address, ipaddress.IPv6Address)) else v
                )
        logger.debug("Query complete: %.2fs, %d rows", elapsed, len(df))
        return df
    except Exception:
        elapsed = time.perf_counter() - start
        logger.error("ClickHouse query failed after %.2fs: %s", elapsed, sql[:200], exc_info=True)
        raise
