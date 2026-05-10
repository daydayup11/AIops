import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_summary_report_fields():
    from models.schemas import SummaryReport
    report = SummaryReport(
        title="校园网分析报告",
        key_points=["应用5流量最高", "高峰在22点"],
        conclusion="过去24小时应用5主导流量。",
    )
    assert len(report.key_points) == 2


def test_task_plan_no_tasks_field():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import TaskPlan, AnalysisPlan
    plan = TaskPlan(
        analysis_plan=AnalysisPlan(
            goal="找异常主机",
            approach="流量特征分析",
            expected_findings=["高流量IP"],
            analysis_dimensions=["IP流量排行"],
            viz_intent="展示Top10 IP流量柱状图",
        ),
        clarification_needed=False,
    )
    assert not hasattr(plan, "tasks")
    assert not hasattr(plan, "viz_blueprint")
    assert plan.analysis_plan.viz_intent == "展示Top10 IP流量柱状图"


def test_py_script_schema():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import PyScript
    s = PyScript(script_code="print('hello')", description="test")
    assert s.script_code == "print('hello')"


def test_code_review_result_schema():
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from models.schemas import CodeReviewResult
    r = CodeReviewResult(approved=True, issues=[])
    assert r.approved is True
    r2 = CodeReviewResult(approved=False, issues=["危险操作: os.system"])
    assert len(r2.issues) == 1
