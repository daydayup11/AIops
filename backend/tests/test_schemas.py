import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_viz_blueprint_fields():
    from models.schemas import VizBlueprint
    bp = VizBlueprint(
        task_id="t1",
        chart_type="bar",
        title="Top10流量",
        x_field="appid",
        y_field="total_bytes",
        insight_hint="应用ID 5 流量最高",
    )
    assert bp.task_id == "t1"
    assert bp.chart_type == "bar"

def test_task_plan_with_blueprint():
    from models.schemas import TaskPlan, SubTask, VizBlueprint
    plan = TaskPlan(
        tasks=[SubTask(id="t1", description="查流量", tables=["sessions"], time_range_hours=24)],
        viz_blueprint=[VizBlueprint(
            task_id="t1", chart_type="bar", title="流量排行",
            x_field="appid", y_field="total_bytes", insight_hint="头部效应明显",
        )],
    )
    assert len(plan.viz_blueprint) == 1
    assert plan.viz_blueprint[0].task_id == "t1"

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
