import json
import logging
import uuid
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
            logger.info("Message received: session=%s, length=%d", session_id, len(message))

            save_message(session_id, "user", "text", message)
            conversation_history.append({"role": "user", "content": message})

            await ws.send_text(json.dumps({"type": "progress", "content": "正在分析您的问题..."}))

            def sync_progress_cb(task_id: str, status: str):
                pass

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
                error=None,
                progress_cb=sync_progress_cb,
            )

            try:
                result_state = get_pipeline().invoke(state)
            except Exception as e:
                await ws.send_text(json.dumps({"type": "error", "content": str(e)}))
                await ws.send_text(json.dumps({"type": "done", "content": ""}))
                continue

            if result_state["clarification_needed"]:
                q = result_state["clarification_question"]
                await ws.send_text(json.dumps({"type": "clarify", "content": q}))
                save_message(session_id, "assistant", "text", q)
                conversation_history.append({"role": "assistant", "content": q})
                continue

            for output in result_state["viz_outputs"]:
                render = output["render"]
                content = output["content"]
                if render == "html":
                    html_content = open(content, encoding="utf-8").read() if isinstance(content, str) else content
                    save_message(session_id, "assistant", "html", html_content)
                    await ws.send_text(json.dumps({"type": "result", "render": "html", "content": html_content}))
                elif render == "echarts":
                    payload = json.dumps(content, ensure_ascii=False)
                    save_message(session_id, "assistant", "echarts", payload)
                    await ws.send_text(json.dumps({"type": "result", "render": "echarts", "content": content}))
                else:
                    save_message(session_id, "assistant", "text", str(content))
                    await ws.send_text(json.dumps({"type": "result", "render": "text", "content": content}))

            logger.info("Response sent: session=%s, outputs=%d", session_id, len(result_state["viz_outputs"]))
            await ws.send_text(json.dumps({"type": "done", "content": "分析完成"}))

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s:%s", client.host if client else "?", client.port if client else "?")
    except Exception:
        logger.error("Unexpected WebSocket error", exc_info=True)
        raise
