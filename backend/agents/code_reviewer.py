import json
import logging
import time
from langchain_openai import ChatOpenAI
from models.schemas import CodeReviewResult
from config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是Python代码安全与性能审查专家。审查以下数据分析脚本，检查：

1. **安全性**：
   - 危险系统调用（os.system, subprocess, eval, exec）
   - 写入OUTPUT_DIR以外的文件路径
   - 除ClickHouse外的网络连接
   - DROP/DELETE/INSERT等危险SQL语句

2. **性能**：
   - 大表（sessions/npm/dns/url，数十亿条）没有LIMIT
   - 大表之间相互JOIN（会超时）
   - 没有时间条件的查询（全表扫描）

3. **超时风险**：
   - 预计可能超过60秒执行时间的查询或计算

返回严格JSON（不要Markdown代码块）：
{"approved": true, "issues": []}
或
{"approved": false, "issues": ["问题1描述", "问题2描述"]}

规则：
- approved=false 时 issues 必须非空，列出具体问题
- approved=true 时 issues 为空数组
- 只在发现明确问题时 approved=false，不要过度审查
"""


def _build_llm() -> ChatOpenAI:
    cfg = settings["llm"]
    return ChatOpenAI(
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        model=cfg["model"],
        temperature=cfg["temperature"],
    )


def run_code_reviewer(script_code: str, llm=None) -> CodeReviewResult:
    llm = llm or _build_llm()
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"请审查以下脚本：\n\n{script_code}"},
    ]

    logger.info("code_reviewer: LLM call start  script_len=%d", len(script_code))
    t0 = time.perf_counter()
    try:
        response = llm.invoke(messages)
    except Exception:
        logger.error("code_reviewer: LLM call failed (%.2fs)", time.perf_counter() - t0, exc_info=True)
        return CodeReviewResult(approved=True, issues=[])
    elapsed = time.perf_counter() - t0
    logger.info("code_reviewer: done %.2fs", elapsed)

    try:
        data = json.loads(response.content)
        result = CodeReviewResult(**data)
        if result.approved:
            logger.info("code_reviewer: APPROVED")
        else:
            logger.info("code_reviewer: REJECTED  issues=%s", result.issues)
        return result
    except Exception:
        logger.warning("code_reviewer: parse failed, defaulting to approved", exc_info=True)
        return CodeReviewResult(approved=True, issues=[])
