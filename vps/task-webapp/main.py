"""FastAPI backend for Telegram Mini App task manager."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

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

@app.delete("/api/task/{project}/{task_id}")
async def delete_task(project: str, task_id: int, authorization: str = Header(default="")):
    get_user(authorization)
    pull()
    ok = vault.archive_task(project, task_id)
    if not ok:
        raise HTTPException(404, "Task not found")
    git_sync(f"archive: task {task_id} in {project}")
    return {"ok": True, "archived": True}

@app.post("/api/transcribe")
async def transcribe_voice(request: Request, authorization: str = Header(default="")):
    get_user(authorization)
    import tempfile, subprocess
    content_type = request.headers.get("content-type", "")
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
        payload += b"Content-Disposition: form-data; name=\"language\"\r\n\r\nru\r\n"
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
