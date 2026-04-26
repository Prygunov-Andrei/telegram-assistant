"""FastAPI backend for Telegram Mini App task manager."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from auth import validate_init_data
from vault import VaultAdapter
from git_sync import pull, commit_and_push, init_repo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VAULT_PATH = "/root/obsidian-tasks"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_repo()
    pull()
    yield


app = FastAPI(title="Task WebApp", lifespan=lifespan)

vault = VaultAdapter(VAULT_PATH)


# ── Auth dependency ──────────────────────────────────────
def get_user(authorization: str = Header(default="")) -> dict:
    """Validate Telegram initData from Authorization header."""
    init_data = authorization.replace("tma ", "").strip()
    user = validate_init_data(init_data)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


# ── API Routes ───────────────────────────────────────────

@app.get("/api/projects")
async def api_projects(authorization: str = Header(default="")):
    get_user(authorization)
    pull()
    counts = vault.project_counts()
    return JSONResponse(content=counts)


@app.get("/api/tasks")
async def api_tasks(
    project: str = "",
    status: str = "",
    authorization: str = Header(default=""),
):
    get_user(authorization)
    pull()
    tasks = vault.list_tasks(
        project=project or None,
        status=status or None,
    )
    return JSONResponse(content=tasks)


class CreateTaskRequest(BaseModel):
    project: str
    title: str
    type: str = "org"
    due: str = ""
    assignee: str = ""


@app.post("/api/task")
async def api_create_task(
    req: CreateTaskRequest,
    authorization: str = Header(default=""),
):
    get_user(authorization)
    pull()
    try:
        task = vault.create_task(
            project=req.project,
            title=req.title,
            task_type=req.type,
            due=req.due,
            assignee=req.assignee,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    commit_and_push(f"webapp: create task #{task['task_id']} {req.title}")
    return JSONResponse(content=task)


class UpdateTaskRequest(BaseModel):
    status: str | None = None
    due: str | None = None
    assignee: str | None = None
    title: str | None = None
    type: str | None = None
    tags: list[str] | None = None
    body: str | None = None



@app.get("/api/task/{project}/{task_id}")
async def get_task(project: str, task_id: int, authorization: str = Header(default="")):
    get_user(authorization)
    fp = vault.find_task_file(project, task_id)
    if not fp:
        raise HTTPException(404, "Task not found")
    text = fp.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    fm = {}
    body = ""
    if len(parts) >= 3:
        import yaml
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except:
            pass
        body = parts[2].strip()
    return {
        "task_id": fm.get("task_id", task_id),
        "title": fm.get("title", ""),
        "status": str(fm.get("status", "todo")),
        "type": fm.get("type", ""),
        "project": project,
        "due": str(fm.get("due") or ""),
        "assignee": str(fm.get("assignee") or ""),
        "body": body,
        "tags": fm.get("tags", []),
    }

@app.patch("/api/task/{project}/{task_id}")
async def api_update_task(
    project: str,
    task_id: int,
    req: UpdateTaskRequest,
    authorization: str = Header(default=""),
):
    get_user(authorization)
    pull()
    fields = {k: v for k, v in req.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    task = vault.update_task(project, task_id, fields)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    commit_and_push(f"webapp: update task #{task_id} in {project}")
    return JSONResponse(content=task)


# ── Static files ─────────────────────────────────────────
# Serve /app/ -> static/index.html
@app.get("/app/{rest_of_path:path}")
async def serve_app(rest_of_path: str = ""):
    return FileResponse("/root/task-webapp/static/index.html")


@app.get("/app")
async def serve_app_root():
    return FileResponse("/root/task-webapp/static/index.html")


# Mount static files for CSS/JS assets if needed
app.mount("/static", StaticFiles(directory="/root/task-webapp/static"), name="static")

# ── Voice transcription endpoint ──────────────────

@app.post("/api/task/{project}/{task_id}/archive")
async def archive_task_endpoint(project: str, task_id: int, authorization: str = Header(default="")):
    """Move task to {project}/archive/. Recoverable from filesystem."""
    get_user(authorization)
    pull()
    ok = vault.archive_task(project, task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    commit_and_push(f"archive: task {task_id} in {project}")
    return {"ok": True, "archived": True}


@app.delete("/api/task/{project}/{task_id}")
async def delete_task_endpoint(project: str, task_id: int, authorization: str = Header(default="")):
    """Hard delete: remove file from working tree + commit the removal.
    Only recoverable through git history."""
    get_user(authorization)
    pull()
    ok = vault.delete_task(project, task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    commit_and_push(f"delete: task {task_id} in {project}")
    return {"ok": True, "deleted": True}


class CommandRequest(BaseModel):
    text: str
    project: str
    task_id: int
    title: str = ""


def _echo_to_telegram(text: str) -> None:
    """Post the command text into the user's DM as a bot message so the
    user sees what they sent (OpenClaw's LLM reply arrives separately)."""
    import json as _json
    import urllib.request
    bot_token = os.environ.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not bot_token or not chat_id:
        return
    try:
        payload = _json.dumps({
            "chat_id": chat_id,
            "text": "📨 " + text,
            "disable_notification": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "task-webapp/1.0"},
        )
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        logger.warning("Telegram echo failed: %s", e)


def _run_openclaw_agent(message: str) -> None:
    """Run openclaw agent subprocess and log result (called in background thread).
    --to <telegram_user_id> binds to the existing DM session so the agent
    routes through the running gateway (fast). Without --to the CLI
    falls back to an embedded agent that typically times out."""
    import subprocess
    telegram_user = os.environ.get("CHAT_ID") or os.environ.get("TELEGRAM_USER_ID", "")
    if not telegram_user:
        logger.error("CHAT_ID not set — cannot route /api/command to LLM")
        return
    try:
        r = subprocess.run(
            [
                "openclaw", "agent",
                "--agent", "main",
                "--channel", "telegram",
                "--to", telegram_user,
                "--deliver",
                "--message", message,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        logger.info(
            "openclaw agent exit=%s stderr=%s stdout_tail=%s",
            r.returncode,
            (r.stderr or "")[:500],
            (r.stdout or "")[-500:],
        )
    except subprocess.TimeoutExpired:
        logger.error("openclaw agent timeout after 180s")
    except Exception as e:
        logger.exception("openclaw agent failed: %s", e)


@app.post("/api/command")
async def send_command(req: CommandRequest, authorization: str = Header(default="")):
    """Wrap user text with task context and fire it into OpenClaw as a
    user message. Fire-and-forget: LLM may think 10-30 s; webapp returns
    immediately, response arrives in Telegram DM."""
    get_user(authorization)
    import threading
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Empty command")
    fp = vault.find_task_file(req.project, req.task_id)
    rel_path = str(fp.relative_to(vault.root)) if fp else f"{req.project}/{req.task_id}-*.md"
    title_part = f', название «{req.title}»' if req.title else ''
    full_message = (
        f"[Команда касается ТОЛЬКО задачи #{req.task_id} "
        f"(проект «{req.project}», файл obsidian-tasks/{rel_path}{title_part}). "
        f"Изменяй ТОЛЬКО этот файл. Другие задачи, расписание дня и связанные файлы не трогай.]\n"
        f"{text}"
    )
    # Echo into chat so the user sees what was sent, then run the agent.
    _echo_to_telegram(full_message)
    threading.Thread(target=_run_openclaw_agent, args=(full_message,), daemon=True).start()
    return {"ok": True, "sent": True}

@app.post("/api/transcribe")
async def transcribe_voice(request: Request, authorization: str = Header(default="")):
    get_user(authorization)
    import tempfile
    body = await request.body()
    if len(body) < 1000:
        raise HTTPException(400, "Audio too short")
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(body)
        tmp_path = f.name
    try:
        import urllib.request, json as j
        boundary = "----VoiceTx"
        with open(tmp_path, "rb") as af:
            audio_data = af.read()
        payload = b""
        payload += f"--{boundary}\r\n".encode()
        payload += b"Content-Disposition: form-data; name=\"model\"\r\n\r\nwhisper-large-v3-turbo\r\n"
        payload += f"--{boundary}\r\n".encode()
        payload += b"Content-Disposition: form-data; name=\"file\"; filename=\"voice.ogg\"\r\nContent-Type: audio/ogg\r\n\r\n"
        payload += audio_data + b"\r\n"
        payload += f"--{boundary}--\r\n".encode()
        groq_key = os.environ.get("GROQ_API_KEY", "")
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            data=payload,
            headers={
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "task-webapp/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = j.loads(resp.read())
        return {"text": result.get("text", "").strip()}
    finally:
        os.unlink(tmp_path)

@app.post("/api/sync")
async def api_sync(request: Request, authorization: str = Header(default="")):
    get_user(authorization)
    body = await request.json()
    action = body.get("action", "push")
    if action == "pull":
        ok = pull()
        return {"ok": ok, "message": "Pull завершён" if ok else "Ошибка pull"}
    else:
        try: vault.regenerate_dashboard()
        except Exception as e: print(f"dashboard regen fail: {e}")
        ok = commit_and_push("webapp: manual sync + dashboard")
        return {"ok": ok, "message": "Push завершён" if ok else "Нет изменений"}
