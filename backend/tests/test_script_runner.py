import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_script_runner_matplotlib_output():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(
        script_code="""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
output_dir = os.environ['OUTPUT_DIR']
plt.plot([1, 2, 3], [4, 5, 6])
plt.savefig(os.path.join(output_dir, '01_chart.png'))
plt.close()
""",
        description="matplotlib test"
    )
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "image"
    assert isinstance(outputs[0]["content"], str)
    assert len(outputs[0]["content"]) > 0


def test_script_runner_multiple_outputs():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(
        script_code="""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
output_dir = os.environ['OUTPUT_DIR']
for i in range(2):
    plt.figure()
    plt.plot([1, 2], [i, i+1])
    plt.savefig(os.path.join(output_dir, f'0{i+1}_chart.png'))
    plt.close()
""",
        description="two charts"
    )
    outputs = run_script_runner(script)
    assert len(outputs) == 2
    assert all(o["render"] == "image" for o in outputs)


def test_script_runner_timeout_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="import time\ntime.sleep(9999)", description="timeout test")
    outputs = run_script_runner(script, timeout=2)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"
    assert "超时" in outputs[0]["content"]


def test_script_runner_script_error_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="raise ValueError('boom')", description="error test")
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"
    assert "boom" in outputs[0]["content"]


def test_script_runner_no_output_returns_error():
    from agents.script_runner import run_script_runner
    from models.schemas import PyScript

    script = PyScript(script_code="print('no images')", description="no output test")
    outputs = run_script_runner(script)
    assert len(outputs) == 1
    assert outputs[0]["render"] == "text"
    assert "图表" in outputs[0]["content"]
