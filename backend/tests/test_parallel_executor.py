import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from models.schemas import SQLTask

import re as _re

_CONN_ERRORS = ("Connection refused", "connect", "Network", "timeout", "timed out",
                "Unable to connect", "getaddrinfo", "Connection timed out")

# ClickHouse error codes that indicate network/connection issues (not query errors)
# Code 209 = SOCKET_TIMEOUT, Code 210 = NETWORK_ERROR, Code 516 = AUTHENTICATION_FAILED
_CH_CONN_CODES = {209, 210}


def _is_connection_error(msg: str) -> bool:
    if any(kw.lower() in msg.lower() for kw in _CONN_ERRORS):
        return True
    # Match ClickHouse "Code: NNN." pattern for known connection-related codes
    m = _re.search(r"Code:\s*(\d+)", msg)
    if m and int(m.group(1)) in _CH_CONN_CODES:
        return True
    return False


def test_parallel_executor_runs_multiple_tasks():
    from executor.parallel import ParallelExecutor

    tasks = [
        SQLTask(task_id="t1", sql="SELECT 1 AS v", description="test1"),
        SQLTask(task_id="t2", sql="SELECT 2 AS v", description="test2"),
    ]
    executor = ParallelExecutor(max_workers=2)
    results = executor.run(tasks)
    assert len(results) == 2
    for tid in ("t1", "t2"):
        if results[tid]["status"] == "error":
            err = results[tid].get("error", "")
            if _is_connection_error(err):
                pytest.skip(f"ClickHouse not reachable: {err}")
            else:
                pytest.fail(f"Unexpected error for {tid}: {err}")
    assert results["t1"]["status"] == "success"
    assert results["t2"]["status"] == "success"


def test_parallel_executor_handles_failure():
    from executor.parallel import ParallelExecutor

    tasks = [
        SQLTask(task_id="bad", sql="SELECT * FROM nonexistent_table_xyz", description="bad"),
    ]
    executor = ParallelExecutor(max_workers=1)
    results = executor.run(tasks)
    assert results["bad"]["status"] == "error"
    assert "error" in results["bad"]


def test_parallel_executor_rejects_non_select():
    from executor.parallel import ParallelExecutor

    tasks = [
        SQLTask(task_id="evil", sql="DROP TABLE sessions", description="evil"),
    ]
    executor = ParallelExecutor(max_workers=1)
    results = executor.run(tasks)
    assert results["evil"]["status"] == "error"
