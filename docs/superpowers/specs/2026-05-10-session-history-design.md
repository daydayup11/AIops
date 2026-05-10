# Session History Design

## Overview

Add persistent session history to the campus network traffic analysis assistant. Users can switch between past conversations, see all historical messages (including charts) with lazy-loaded images, auto-generated session titles, and basic session management (rename, delete).

## Requirements

- Switching to a past session fully restores all messages (text, clarify, summary, charts)
- Chart images (base64 PNG) lazy-load via IntersectionObserver when scrolled into view
- After the first conversation turn, a LLM-generated short title (≤10 chars) replaces "新对话"
- Sessions support rename (inline edit) and delete (with confirmation)
- Deleting the active session auto-switches to the next session, or creates a new one if none exist

## Architecture

```
Frontend                         Backend
─────────────────────────────    ────────────────────────────────
App.tsx                          api/sessions.py  (new)
  useSessionMessages (new)  ───► GET  /api/v1/sessions
  useWebSocket (extended)   ───► GET  /api/v1/sessions/{id}/messages
  ChartRenderer (extended)  ───► GET  /api/v1/sessions/{id}/messages/{msg_id}/image
  SessionSidebar (extended) ───► DELETE /api/v1/sessions/{id}
                            ───► PATCH  /api/v1/sessions/{id}

WebSocket /api/v1/chat
  chat.py (extended)        ──── pushes {"type": "session_title", ...} after pipeline done
                            ──── calls LLM async to generate title
```

## Data Layer

### SQLite schema change

Add `image_data TEXT` column to `messages`:

```sql
ALTER TABLE messages ADD COLUMN image_data TEXT;
```

For `image` type messages:
- `content` stores the literal string `"[图表]"` (not truncated base64)
- `image_data` stores the full base64 PNG string

For all other message types, `image_data` is NULL.

### New / modified functions in `db/sqlite.py`

| Function | Description |
|---|---|
| `save_message(session_id, role, msg_type, content, image_data=None)` | Add optional `image_data` param; image messages write to both columns |
| `get_session_messages(session_id)` | Returns messages without `image_data`; image rows have `content="[图表]"` |
| `get_message_image(msg_id) -> str \| None` | Returns `image_data` for a single message |
| `delete_session(session_id)` | Deletes messages then session (cascade) |
| `rename_session(session_id, title)` | Updates `sessions.title` |

`update_session_title` reuses `rename_session`.

## Backend API

New file: `backend/api/sessions.py`, registered at prefix `/api/v1`.

| Endpoint | Request | Response |
|---|---|---|
| `GET /sessions` | — | `[{id, title, created_at, updated_at}]` (latest 50) |
| `GET /sessions/{id}/messages` | — | `[{id, session_id, role, type, content, created_at}]` — no image_data |
| `GET /sessions/{id}/messages/{msg_id}/image` | — | `{"image_data": "<base64>"}` or 404 |
| `DELETE /sessions/{id}` | — | 204 or 404 |
| `PATCH /sessions/{id}` | `{"title": "..."}` | `{id, title}` |

`main.py` adds:
```python
from api.sessions import router as sessions_router
app.include_router(sessions_router, prefix="/api/v1")
```

### LLM auto-naming

After pipeline completes and before `done` is sent, `chat.py` launches an async background task:

1. Takes `user_message[:200]` as context
2. Calls Claude with `max_tokens=20`, prompt: "用不超过10个字概括这个问题，只输出标题，不加标点"
3. Writes result to `sessions.title` via `rename_session`
4. Pushes over the existing WebSocket:
   ```json
   {"type": "session_title", "session_id": "...", "title": "..."}
   ```

On failure: silently keeps "新对话", never raises to the user.

## Frontend

### `useWebSocket` changes

- Add handling for `session_title` message type: fires `onSessionTitle(id, title)` callback (passed in by App), does not add to `messages` state
- When `sessionId` prop changes, clear `messages` immediately (history load takes over)

### New hook: `useSessionMessages`

```ts
function useSessionMessages(sessionId: string): {
  historyMessages: ChatMessage[];
  isLoadingHistory: boolean;
  historyError: string | null;
}
```

On `sessionId` change:
1. `GET /sessions/{id}/messages`
2. Maps each row to `ChatMessage`; for `type === "image"` rows: sets `render: "image-placeholder"` and includes `msg_id` field
3. Returns `historyMessages` which App merges as the initial message list before live WebSocket messages

### `ChartRenderer` lazy loading

`ChatMessage` type gains an optional `msg_id?: number` field used only for history image lazy-loading.

For `render === "image-placeholder"` messages:
1. Render a skeleton placeholder (grey box, same aspect ratio as typical chart)
2. Attach `IntersectionObserver` to the placeholder element
3. On intersection: fetch `GET /sessions/{id}/messages/{msg_id}/image`
4. On success: replace placeholder with `<img src="data:image/png;base64,..." />`
5. On failure: show "图表加载失败" text, no retry

For live `render === "image"` messages (current session), behavior unchanged — base64 is already in the message.

### `SessionSidebar` changes

Each session row: on hover, show two icon buttons (Pencil, Trash2) at the right edge.

**Rename flow:**
- Click Pencil → row switches to `<input>` pre-filled with current title
- Enter or blur → `PATCH /sessions/{id}` → update local sessions state on success; revert on failure with toast

**Delete flow:**
- Click Trash2 → inline confirm (text changes to "确认删除?" with Check / X icons, 3s auto-cancel)
- Confirm → `DELETE /sessions/{id}` → remove from local sessions state
- If deleted session was active: switch to next session in list; if list empty, call `onNew()`

### `App.tsx` changes

- `sessions` state updated by `onSessionTitle` callback without re-fetching
- On session switch: set `sessionId`, `useSessionMessages` provides history, `useWebSocket` provides new live messages; App concatenates `[...historyMessages, ...liveMessages]` as the message list passed to `ChatPanel`
- On new session: clear history, generate new UUID as before

## Error Handling

| Scenario | Behavior |
|---|---|
| History load fails | Show "历史记录加载失败，请刷新重试" banner above chat; input still usable |
| Chart lazy-load fails | Show "图表加载失败" in placeholder; no retry |
| LLM naming fails | Silent fallback to "新对话"; no user-visible error |
| Delete/rename API fails | Toast notification; local state rolled back |
| Delete active session | Auto-switch to next session; if none, create new |

## Testing

**Backend (pytest):**

- `tests/test_sessions.py`: GET/DELETE/PATCH endpoints — happy path + 404 cases
- `tests/test_sqlite.py`: `get_message_image`, `delete_session`, `rename_session`
- `tests/test_chat.py`: mock LLM client, assert `session_title` WebSocket message is sent after pipeline `done`

**Frontend:** No test framework currently. Hooks are designed to be independently callable for future test additions.
