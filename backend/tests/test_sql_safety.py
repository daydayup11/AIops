import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_sql_engineer_returns_sql_tasks():
    from agents.sql_engineer import run_sql_engineer
    from models.schemas import SubTask

    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                content = '[{"task_id":"t1","sql":"SELECT ipv4, sum(up_bytes+down_bytes) as total FROM iplog WHERE collect_time >= now()-INTERVAL 1 DAY GROUP BY ipv4 ORDER BY total DESC LIMIT 100","description":"IP流量Top100"}]'
            return Resp()

    tasks = [SubTask(id="t1", description="统计昨天各IP流量", tables=["iplog"], time_range_hours=24)]
    result = run_sql_engineer(tasks, llm=FakeLLM())
    assert len(result) == 1
    assert result[0].task_id == "t1"
    assert "SELECT" in result[0].sql.upper()


def test_sql_engineer_injects_time_condition():
    from agents.sql_engineer import ensure_time_condition
    sql_without_time = "SELECT count(*) FROM sessions"
    result = ensure_time_condition(sql_without_time, "sessions")
    assert "start" in result.lower()


def test_sql_engineer_adds_limit():
    from agents.sql_engineer import ensure_limit
    sql = "SELECT * FROM sessions WHERE start >= now()-INTERVAL 1 DAY"
    result = ensure_limit(sql)
    assert "LIMIT" in result.upper()


def test_ensure_time_condition_preserves_existing():
    from agents.sql_engineer import ensure_time_condition
    sql_with_time = "SELECT count(*) FROM sessions WHERE start >= now()-INTERVAL 1 DAY"
    result = ensure_time_condition(sql_with_time, "sessions")
    assert result == sql_with_time


def test_ensure_limit_preserves_existing():
    from agents.sql_engineer import ensure_limit
    sql_with_limit = "SELECT * FROM sessions WHERE start >= now()-INTERVAL 1 DAY LIMIT 500"
    result = ensure_limit(sql_with_limit)
    assert result == sql_with_limit
