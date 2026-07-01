"""REST API for FFAStrans Linux Mimo - compatible with original API."""
import os
import json
import time
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from ..core.storage import Storage
from ..core.config import BASE_DIR, API_PORT, HOSTNAME
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
    host = HostInfo(
        name=data.get("name", ""),
        hostname=data.get("hostname", HOSTNAME),
        ip=data.get("ip", "127.0.0.1"),
        port=data.get("port", API_PORT),
        groups=data.get("groups", []),
        max_jobs=data.get("max_jobs", 4),
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
