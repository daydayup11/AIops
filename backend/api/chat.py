import asyncio
import json
import logging
from functools import partial
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from langchain_openai import ChatOpenAI
from db.sqlite import create_session, save_message, rename_session
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


def _get_llm() -> ChatOpenAI:
    from config import settings
    return ChatOpenAI(
        base_url=settings["llm"]["base_url"],
        api_key=settings["llm"]["api_key"],
        model=settings["llm"]["model"],
        max_tokens=20,
        temperature=0.0,
    )


async def generate_and_push_title(session_id: str, user_message: str, send_fn) -> None:
    try:
        llm = _get_llm()
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: llm.invoke([
                {"role": "system", "content": "用不超过10个字概括这个问题，只输出标题，不加标点"},
                {"role": "user", "content": user_message[:200]},
            ]),
        )
        title = result.content.strip()[:20]  # guard against overlong response
        rename_session(session_id, title)
        await send_fn({"type": "session_title", "session_id": session_id, "title": title})
    except Exception:
        logger.debug("LLM naming failed silently for session %s", session_id, exc_info=True)


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

            state = PipelineState(
                session_id=session_id,
                user_message=message,
                conversation_history=conversation_history.copy(),
                task_plan=None,
                py_script=None,
                code_review_result=None,
                script_retry_count=0,
                viz_outputs=[],
                clarification_needed=False,
                clarification_question=None,
                clarifier_done=False,
                clarifier_question=None,
                clarifier_options=[],
                summary_report=None,
                error=None,
                progress_cb=progress_cb,
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
                logger.info("[%s] clarifier ask sent", session_id)
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
                if render == "image":
                    save_message(session_id, "assistant", "image", content[:100] + "...")
                    await _send(ws, {"type": "result", "render": "image", "content": content})
                    logger.info("[%s] sent output[%d] image  b64_len=%d", session_id, i, len(content))
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await _send(ws, {"type": "result", "render": "text", "content": content})

            # 综合报告
            report = result_state.get("summary_report")
            if report:
                report_payload = report.model_dump()
                save_message(session_id, "assistant", "text", report.conclusion)
                await _send(ws, {"type": "summary", "content": report_payload})
                logger.info("[%s] summary sent  points=%d", session_id, len(report.key_points))

            logger.info("[%s] pipeline done  outputs=%d", session_id, len(result_state["viz_outputs"]))
            asyncio.create_task(
                generate_and_push_title(session_id, message, lambda p: _send(ws, p))
            )
            await _send(ws, {"type": "done", "content": "分析完成"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error("Unexpected WebSocket error", exc_info=True)
        try:
            await _send(ws, {"type": "error", "content": f"服务器内部错误：{e}"})
            await _send(ws, {"type": "done", "content": ""})
        except Exception:
            pass
