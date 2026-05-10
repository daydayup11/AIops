import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_execute_returns_dataframe():
    from db.clickhouse import execute_query
    import pandas as pd
    try:
        df = execute_query("SELECT 1 AS val")
        assert isinstance(df, pd.DataFrame)
        assert df.iloc[0]["val"] == 1
    except Exception as e:
        err_type = type(e).__name__
        err_msg = str(e)
        # If it's a network/connection error, skip gracefully
        if any(kw in err_msg for kw in ["Connection refused", "timed out", "timeout", "10061", "Network"]) \
                or any(kw in err_type for kw in ["Timeout", "Network", "Socket", "Connection"]):
            pytest.skip(f"ClickHouse not reachable ({err_type}): {err_msg[:120]}")
        raise


def test_execute_rejects_non_select():
    from db.clickhouse import execute_query, SQLSecurityError
    with pytest.raises(SQLSecurityError):
        execute_query("DROP TABLE sessions")


def test_execute_rejects_insert():
    from db.clickhouse import execute_query, SQLSecurityError
    with pytest.raises(SQLSecurityError):
        execute_query("INSERT INTO sessions VALUES (1)")
