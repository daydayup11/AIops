import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_pipeline_state_has_new_fields():
    from graph.pipeline import PipelineState
    fields = PipelineState.__annotations__
    assert "py_script" in fields
    assert "code_review_result" in fields
    assert "script_retry_count" in fields
    assert "sql_tasks" not in fields
    assert "execution_results" not in fields


def test_pipeline_builds():
    from graph.pipeline import build_pipeline
    pipeline = build_pipeline()
    assert pipeline is not None


def test_pipeline_route_after_code_reviewer_approved():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": True, "issues": []})(),
        "script_retry_count": 0,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "script_runner"


def test_pipeline_route_after_code_reviewer_retry():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": False, "issues": ["问题"]})(),
        "script_retry_count": 1,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "sql_engineer"


def test_pipeline_route_after_code_reviewer_max_retries():
    from graph.pipeline import route_after_code_reviewer
    state = {
        "code_review_result": type("R", (), {"approved": False, "issues": ["问题"]})(),
        "script_retry_count": 3,
        "error": None,
    }
    assert route_after_code_reviewer(state) == "end"
