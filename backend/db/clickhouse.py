import re
import pandas as pd
from clickhouse_driver import Client
from config import settings

_cfg = settings["clickhouse"]

_client = Client(
    host=_cfg["host"],
    port=_cfg["port"],
    user=_cfg["user"],
    password=_cfg["password"],
    database=_cfg["database"],
    connect_timeout=_cfg["connect_timeout"],
)

_FORBIDDEN = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|RENAME|ATTACH|DETACH)",
    re.IGNORECASE,
)


class SQLSecurityError(Exception):
    pass


def execute_query(sql: str, timeout: int = None) -> pd.DataFrame:
    if _FORBIDDEN.match(sql):
        raise SQLSecurityError(f"拒绝执行非SELECT语句: {sql[:60]}")
    t = timeout or _cfg.get("query_timeout", 30)
    rows, columns = _client.execute(
        sql,
        with_column_types=True,
        settings={"max_execution_time": t},
    )
    col_names = [c[0] for c in columns]
    return pd.DataFrame(rows, columns=col_names)
