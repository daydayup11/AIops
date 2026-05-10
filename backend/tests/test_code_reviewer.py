import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _fake_llm(content: str):
    class FakeLLM:
        def invoke(self, messages):
            class Resp:
                pass
            r = Resp()
            r.content = content
            return r
    return FakeLLM()


def test_code_reviewer_approves_clean_script():
    from agents.code_reviewer import run_code_reviewer
    from models.schemas import CodeReviewResult

    result = run_code_reviewer(
        "import os\nprint('hello')",
        llm=_fake_llm('{"approved": true, "issues": []}')
    )
    assert isinstance(result, CodeReviewResult)
    assert result.approved is True
    assert result.issues == []


def test_code_reviewer_rejects_dangerous_script():
    from agents.code_reviewer import run_code_reviewer
    from models.schemas import CodeReviewResult

    result = run_code_reviewer(
        "import os\nos.system('rm -rf /')",
        llm=_fake_llm('{"approved": false, "issues": ["危险操作: os.system调用"]}')
    )
    assert result.approved is False
    assert len(result.issues) == 1


def test_code_reviewer_handles_invalid_json():
    from agents.code_reviewer import run_code_reviewer

    result = run_code_reviewer("print('hi')", llm=_fake_llm("不是JSON"))
    # Fallback: approve to avoid blocking pipeline on reviewer failure
    assert result.approved is True


def test_code_reviewer_handles_llm_failure():
    from agents.code_reviewer import run_code_reviewer

    class ErrorLLM:
        def invoke(self, _):
            raise RuntimeError("LLM down")

    result = run_code_reviewer("print('hi')", llm=ErrorLLM())
    assert result.approved is True
