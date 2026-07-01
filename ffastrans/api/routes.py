"""REST API for FFAStrans Linux Mimo - compatible with original API."""
import os
import json
import time
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from ..core.storage import Storage
from ..core.config import BASE_DIR, API_PORT, HOSTNAME, MAX_CONCURRENT_JOBS
from ..core.models import (
    Workflow, Job, Node, Variable, Connection, HostInfo,
    WorkflowState, JobState, NodeState
)
from ..core.engine import WorkflowEngine
from ..nodes.registry import list_available_nodes

logger = logging.getLogger("ffastrans.api")

storage = Storage()
engine = WorkflowEngine(storage)

app = FastAPI(title="FFAStrans Linux Mimo", version="2.0.0-linux-mimo")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

gui_path = BASE_DIR / "ffastrans" / "gui"
app.mount("/static", StaticFiles(directory=str(gui_path / "static")), name="static")


@app.on_event("startup")
async def register_master_as_worker():
    max_jobs_per_class = {}
    for i in range(6):
        max_jobs_per_class[str(i)] = MAX_CONCURRENT_JOBS
    host = HostInfo(
        name=HOSTNAME,
        hostname=HOSTNAME,
        ip="127.0.0.1",
        port=API_PORT,
        groups=["default", "master"],
        max_jobs_per_class=max_jobs_per_class,
        active=True,
        last_seen=time.time(),
    )
    storage.register_host(host)
    logger.info(f"Master node registered as worker: {HOSTNAME}")


class WorkflowCreate(BaseModel):
    name: str = "New Workflow"
    nodes: list = []
    connections: list = []
    variables: list = []
    drop_folders: list = []


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    nodes: Optional[list] = None
    connections: Optional[list] = None
    variables: Optional[list] = None
    drop_folders: Optional[list] = None


class WorkflowStateChange(BaseModel):
    action: str


class JobCreate(BaseModel):
    wf_id: str
    inputfile: str = ""
    start_proc: str = ""
    priority: int = 2
    variables: list = []


class JobAction(BaseModel):
    action: str
    split_id: str = ""


class VariableCreate(BaseModel):
    name: str
    vtype: str = "s"
    value: str = ""
    is_static: bool = False


class PresetImport(BaseModel):
    data: dict = {}


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = gui_path / "templates" / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text())
    return HTMLResponse("<h1>FFAStrans Linux Mimo</h1><p>API is running. GUI not found.</p>")


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    monitor_path = gui_path / "templates" / "monitor.html"
    if monitor_path.exists():
        return HTMLResponse(monitor_path.read_text())
    return HTMLResponse("<h1>Monitor not available</h1>")


@app.get("/api/about")
async def about():
    return {
        "name": "FFAStrans Linux Mimo",
        "version": "2.0.0-linux-mimo",
        "hostname": HOSTNAME,
        "platform": "linux",
        "api": True,
    }


@app.get("/api/workflows")
async def list_workflows():
    return storage.get_all_workflows()


@app.get("/api/workflows/status")
async def workflow_statuses():
    return storage.get_workflow_statuses()


@app.get("/api/workflows/{wf_id}")
async def get_workflow(wf_id: str):
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return wf.to_dict()


@app.post("/api/workflows")
async def create_workflow(data: WorkflowCreate):
    wf = Workflow(
        name=data.name,
        nodes=[Node.from_dict(n) if isinstance(n, dict) else n for n in data.nodes],
        connections=[Connection.from_dict(c) if isinstance(c, dict) else c for c in data.connections],
        variables=[Variable.from_dict(v) if isinstance(v, dict) else v for v in data.variables],
        drop_folders=data.drop_folders,
    )
    storage.create_workflow(wf)
    await broadcast_log(f"Workflow created: '{wf.name}' ({wf.id})", "success")
    return wf.to_dict()


@app.post("/api/workflows/import")
async def import_workflow(request: Request):
    data = await request.json()
    wf = storage.import_workflow(data)
    return {"id": wf.id, "name": wf.name}


@app.put("/api/workflows/{wf_id}")
async def update_workflow(wf_id: str, data: WorkflowUpdate):
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")

    if data.name is not None:
        wf.name = data.name
    if data.nodes is not None:
        wf.nodes = [Node.from_dict(n) if isinstance(n, dict) else n for n in data.nodes]
    if data.connections is not None:
        wf.connections = [Connection.from_dict(c) if isinstance(c, dict) else c for c in data.connections]
    if data.variables is not None:
        wf.variables = [Variable.from_dict(v) if isinstance(v, dict) else v for v in data.variables]
    if data.drop_folders is not None:
        wf.drop_folders = data.drop_folders

    storage.update_workflow(wf)
    return wf.to_dict()


@app.put("/api/workflows/{wf_id}/state")
async def change_workflow_state(wf_id: str, data: WorkflowStateChange):
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")

    action = data.action.lower()
    if action == "start":
        wf.state = WorkflowState.RUNNING
    elif action == "stop":
        wf.state = WorkflowState.STOPPED
    elif action == "enable":
        wf.state = WorkflowState.RUNNING
    elif action == "disable":
        wf.state = WorkflowState.DISABLED
    else:
        raise HTTPException(400, f"Unknown action: {action}")

    storage.update_workflow(wf)
    return {"status": "ok", "state": wf.state.value}


@app.delete("/api/workflows/{wf_id}")
async def delete_workflow(wf_id: str):
    storage.delete_workflow(wf_id)
    return {"status": "deleted"}


@app.get("/api/workflows/{wf_id}/user_variables")
async def get_workflow_variables(wf_id: str):
    wf = storage.get_workflow(wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")
    return [v.to_dict() if hasattr(v, "to_dict") else v for v in wf.variables]


@app.get("/api/user_variables")
async def get_user_variables():
    return storage.get_user_variables()


@app.post("/api/user_variables")
async def create_user_variable(data: VariableCreate):
    var = Variable(name=data.name, vtype=data.vtype, value=data.value, is_static=data.is_static)
    storage.set_user_variable(var)
    return var.to_dict()


@app.post("/api/user_variables/import")
async def import_user_variable(request: Request):
    data = await request.json()
    var = storage.import_user_variable(data)
    return var.to_dict()


@app.get("/api/jobs")
async def list_jobs():
    return storage.get_all_jobs()


@app.get("/api/jobs/active")
async def list_active_jobs():
    return storage.get_running_jobs()


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


@app.post("/api/jobs")
async def submit_job(data: JobCreate):
    wf = storage.get_workflow(data.wf_id)
    if not wf:
        raise HTTPException(404, "Workflow not found")

    job = Job(
        wf_id=data.wf_id,
        input_file=data.inputfile,
        start_proc=data.start_proc,
        priority=data.priority,
    )

    for v in data.variables:
        name = v.get("name", "")
        val = v.get("data", "")
        job.variables[name] = val

    storage.create_job(job)
    await broadcast_log(f"Job submitted: {job.id[:8]} to workflow '{wf.name}' ({data.inputfile or 'monitor'})", "info")
    engine.start_job(job)

    return {
        "uri": f"/api/jobs/{job.id}",
        "job_id": job.id,
    }


@app.put("/api/jobs/{job_id}")
async def job_action(job_id: str, data: JobAction):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    action = data.action.lower()
    if action == "abort":
        engine.abort_job(job_id)
    elif action == "pause":
        engine.pause_job(job_id, data.split_id)
    elif action == "resume":
        engine.resume_job(job_id, data.split_id)
    elif action == "retry":
        job.state = JobState.QUEUED
        storage.update_job(job)
        engine.start_job(job)
    elif action == "retry_fail":
        job.state = JobState.QUEUED
        storage.update_job(job)
        engine.start_job(job)
    else:
        raise HTTPException(400, f"Unknown action: {action}")

    return {"status": "ok"}


@app.delete("/api/jobs/{job_id}")
async def abort_job(job_id: str):
    engine.abort_job(job_id)
    return {"status": "aborted"}


@app.get("/api/joblog/{job_id}")
async def get_job_log(job_id: str, start: int = 0, count: int = 300):
    return storage.get_job_log(job_id, start, count)


@app.get("/api/jobvars/{job_id}")
async def get_job_variables(job_id: str, vars: str = ""):
    job = storage.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if vars:
        var_names = [v.strip() for v in vars.split("|") if v.strip()]
        return {k: job.variables.get(k, "") for k in var_names}
    return job.variables


@app.get("/api/history")
async def get_history(start: int = 0, count: int = 250):
    return storage.get_history(start, count)


@app.get("/api/presets")
async def list_presets():
    return storage.get_presets()


@app.post("/api/presets/import")
async def import_preset(request: Request):
    data = await request.json()
    preset_id = data.get("id", f"preset_{int(time.time())}")
    storage.import_preset(preset_id, data)
    return {"id": preset_id}


@app.get("/api/nodes/available")
async def available_nodes():
    return list_available_nodes()


@app.get("/api/hosts")
async def list_hosts():
    return storage.get_hosts()


@app.post("/api/hosts/register")
async def register_host(request: Request):
    data = await request.json()
    max_jobs_per_class = {}
    max_jobs = data.get("max_jobs", 4)
    for i in range(6):
        max_jobs_per_class[str(i)] = max_jobs
    host = HostInfo(
        name=data.get("name", ""),
        hostname=data.get("hostname", HOSTNAME),
        ip=data.get("ip", "127.0.0.1"),
        port=data.get("port", API_PORT),
        groups=data.get("groups", ["default"]),
        max_jobs_per_class=max_jobs_per_class,
        active=True,
        last_seen=time.time(),
    )
    storage.register_host(host)
    return {"status": "ok"}


@app.get("/api/hosts/heartbeat")
async def host_heartbeat(request: Request):
    hostname = HOSTNAME
    data = {"hostname": hostname, "active": True, "last_seen": time.time()}
    storage.update_host(hostname, **data)
    return {"status": "ok"}


@app.get("/api/files/browse")
async def browse_files(path: str = ""):
    from ..core.config import INPUT_DIR
    if not path or path == "/":
        path = str(INPUT_DIR)
    try:
        p = Path(path).resolve()
        if not p.exists():
            raise HTTPException(404, "Path not found")
        if p.is_file():
            return {"path": str(p), "items": [{"name": p.name, "path": str(p), "is_dir": False, "size": p.stat().st_size}]}
        items = []
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size": stat.st_size if item.is_file() else 0,
                    "modified": stat.st_mtime,
                })
            except PermissionError:
                items.append({"name": item.name, "path": str(item), "is_dir": item.is_dir(), "size": 0})
        return {"path": str(p), "items": items}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/files/upload")
async def upload_file(file: UploadFile = File(...), path: str = Form("")):
    from ..core.config import INPUT_DIR
    try:
        if not path or path == "/":
            path = str(INPUT_DIR)
        dest_dir = Path(path).resolve()
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / file.filename
        content = await file.read()
        with open(dest_file, "wb") as f:
            f.write(content)
        await broadcast_log(f"File uploaded: {file.filename} ({len(content)} bytes) to {dest_dir}", "success")
        return {"status": "ok", "path": str(dest_file), "size": len(content)}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        await broadcast_log(f"Upload failed: {file.filename} - {e}", "error")
        raise HTTPException(500, str(e))


@app.get("/api/files/download")
async def download_file(path: str):
    try:
        p = Path(path).resolve()
        if not p.exists() or not p.is_file():
            raise HTTPException(404, "File not found")
        await broadcast_log(f"File download: {p.name}", "info")
        from fastapi.responses import FileResponse
        return FileResponse(path=str(p), filename=p.name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


class SettingsUpdate(BaseModel):
    hostname: Optional[str] = None
    port: Optional[str] = None
    max_concurrent_jobs: Optional[str] = None
    input_dir: Optional[str] = None
    output_dir: Optional[str] = None
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None


@app.post("/api/settings")
async def save_settings(data: SettingsUpdate):
    from ..core.config import save_config
    cfg = {}
    if data.hostname is not None: cfg["hostname"] = data.hostname
    if data.port is not None: cfg["api_port"] = data.port
    if data.max_concurrent_jobs is not None: cfg["max_concurrent_jobs"] = data.max_concurrent_jobs
    if data.input_dir is not None: cfg["input_dir"] = data.input_dir
    if data.output_dir is not None: cfg["output_dir"] = data.output_dir
    if data.ffmpeg_path is not None: cfg["ffmpeg_path"] = data.ffmpeg_path
    if data.ffprobe_path is not None: cfg["ffprobe_path"] = data.ffprobe_path
    save_config(cfg)
    return {"status": "ok"}


@app.get("/api/settings")
async def get_settings():
    from ..core.config import load_config
    return load_config()


ws_clients: list[WebSocket] = []


@app.middleware("http")
async def update_host_heartbeat(request: Request, call_next):
    if request.url.path.startswith("/ws/") or request.url.path.startswith("/static"):
        return await call_next(request)
    response = await call_next(request)
    try:
        storage.update_host(HOSTNAME, last_seen=time.time(), active=True)
    except Exception:
        pass
    return response


async def broadcast_log(message: str, level: str = "info"):
    for ws in ws_clients[:]:
        try:
            await ws.send_text(json.dumps({"type": "server_log", "message": message, "level": level}))
        except Exception:
            pass


@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    logger.info(f"WebSocket client connected ({len(ws_clients)} total)")
    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                if msg == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                pass
            except Exception:
                break
            try:
                active_jobs = storage.get_running_jobs()
                if active_jobs:
                    await websocket.send_text(json.dumps({
                        "type": "jobs_update",
                        "data": active_jobs,
                    }))
            except Exception:
                pass
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_clients)} total)")
