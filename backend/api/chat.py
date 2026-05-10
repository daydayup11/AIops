import asyncio
import json
import logging
from functools import partial
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from db.sqlite import create_session, save_message
from graph.pipeline import build_pipeline, PipelineState

logger = logging.getLogger(__name__)
router = APIRouter()
_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
    return _pipeline


async def _send(ws: WebSocket, payload: dict) -> None:
    await ws.send_text(json.dumps(payload, ensure_ascii=False))


@router.websocket("/chat")
async def websocket_chat(ws: WebSocket):
    await ws.accept()
    client = ws.client
    logger.info("WebSocket connected: %s:%s", client.host if client else "?", client.port if client else "?")
    conversation_history = []

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            session_id = data.get("session_id") or create_session()
            message = data["message"]
            logger.info("[%s] message received  len=%d", session_id, len(message))

            save_message(session_id, "user", "text", message)
            conversation_history.append({"role": "user", "content": message})

            loop = asyncio.get_event_loop()

            def progress_cb(text: str) -> None:
                logger.info("[%s] progress: %s", session_id, text)
                asyncio.run_coroutine_threadsafe(
                    _send(ws, {"type": "progress", "content": text}),
                    loop,
                )

            def plan_cb(blueprint: list) -> None:
                logger.info("[%s] plan: %d items", session_id, len(blueprint))
                asyncio.run_coroutine_threadsafe(
                    _send(ws, {"type": "plan", "content": blueprint}),
                    loop,
                )

            state = PipelineState(
                session_id=session_id,
                user_message=message,
                conversation_history=conversation_history.copy(),
                task_plan=None,
                sql_tasks=[],
                execution_results={},
                viz_outputs=[],
                clarification_needed=False,
                clarification_question=None,
                clarifier_done=False,
                clarifier_question=None,
                clarifier_options=[],
                summary_report=None,
                error=None,
                progress_cb=progress_cb,
                plan_cb=plan_cb,
            )

            logger.info("[%s] pipeline start", session_id)
            try:
                result_state = await loop.run_in_executor(
                    None, partial(get_pipeline().invoke, state)
                )
            except Exception as e:
                logger.error("[%s] pipeline failed: %s", session_id, e, exc_info=True)
                await _send(ws, {"type": "error", "content": str(e)})
                await _send(ws, {"type": "done", "content": ""})
                continue

            # clarifier 追问
            if not result_state.get("clarifier_done", True) and result_state.get("clarifier_question"):
                q = result_state["clarifier_question"]
                options = result_state.get("clarifier_options", [])
                payload = {"type": "clarify", "question": q, "options": options, "allow_free_input": True}
                await _send(ws, payload)
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                logger.info("[%s] clarifier ask sent  question=%r  options=%s", session_id, q[:60], options)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # planner 澄清（兜底）
            if result_state["clarification_needed"]:
                q = result_state["clarification_question"]
                await _send(ws, {"type": "clarify", "question": q, "options": [], "allow_free_input": True})
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                logger.info("[%s] planner clarification sent", session_id)
                await _send(ws, {"type": "done", "content": ""})
                continue

            # 图表结果
            for i, output in enumerate(result_state["viz_outputs"]):
                render = output["render"]
                content = output["content"]
                if render == "html":
                    html_content = open(content, encoding="utf-8").read() if isinstance(content, str) else content
                    save_message(session_id, "assistant", "html", html_content)
                    await _send(ws, {"type": "result", "render": "html", "content": html_content})
                    logger.info("[%s] sent output[%d] html", session_id, i)
                elif render == "echarts":
                    save_message(session_id, "assistant", "echarts", json.dumps(content, ensure_ascii=False))
                    await _send(ws, {"type": "result", "render": "echarts", "content": content})
                    logger.info("[%s] sent output[%d] echarts", session_id, i)
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await _send(ws, {"type": "result", "render": "text", "content": content})

            # 综合报告
            report = result_state.get("summary_report")
            if report:
                report_payload = report.model_dump()
                save_message(session_id, "assistant", "text", report.conclusion)
                await _send(ws, {"type": "summary", "content": report_payload})
                logger.info("[%s] summary sent  title=%r  points=%d", session_id, report.title, len(report.key_points))

            logger.info("[%s] pipeline done  outputs=%d", session_id, len(result_state["viz_outputs"]))
            await _send(ws, {"type": "done", "content": "分析完成"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s:%s", client.host if client else "?", client.port if client else "?")
    except Exception:
        logger.error("Unexpected WebSocket error", exc_info=True)
        raise
