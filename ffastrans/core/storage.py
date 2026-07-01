"""JSON-file based persistent storage for workflows, jobs, variables, and presets."""
import json
import time
from pathlib import Path
from typing import Optional
from .config import WORKFLOW_DIR, JOB_DIR, LOG_DIR, DATA_DIR
from .models import Workflow, Job, Variable, HostInfo


class Storage:
    def __init__(self):
        self._workflows: dict[str, Workflow] = {}
        self._jobs: dict[str, Job] = {}
        self._variables: list[Variable] = []
        self._presets: dict = {}
        self._hosts: dict[str, HostInfo] = {}
        self._history: list = []
        self._load_all()

    def _load_all(self):
        for p in WORKFLOW_DIR.glob("*.json"):
            try:
                with open(p) as f:
                    d = json.load(f)
                wf = Workflow.from_dict(d)
                self._workflows[wf.id] = wf
            except Exception:
                pass

        for p in JOB_DIR.glob("*.json"):
            try:
                with open(p) as f:
                    d = json.load(f)
                job = Job.from_dict(d)
                self._jobs[job.id] = job
            except Exception:
                pass

        var_path = DATA_DIR / "variables.json"
        if var_path.exists():
            with open(var_path) as f:
                self._variables = [Variable.from_dict(v) for v in json.load(f)]

        preset_path = DATA_DIR / "presets.json"
        if preset_path.exists():
            with open(preset_path) as f:
                self._presets = json.load(f)

        hosts_path = DATA_DIR / "hosts.json"
        if hosts_path.exists():
            with open(hosts_path) as f:
                self._hosts = {k: HostInfo.from_dict(v) for k, v in json.load(f).items()}

        history_path = DATA_DIR / "history.json"
        if history_path.exists():
            with open(history_path) as f:
                self._history = json.load(f)

    def _save_workflow(self, wf: Workflow):
        wf.updated_at = time.time()
        p = WORKFLOW_DIR / f"{wf.id}.json"
        with open(p, "w") as f:
            json.dump(wf.to_dict(), f, indent=2)

    def _save_job(self, job: Job):
        p = JOB_DIR / f"{job.id}.json"
        with open(p, "w") as f:
            json.dump(job.to_dict(), f, indent=2)

    def _save_variables(self):
        with open(DATA_DIR / "variables.json", "w") as f:
            json.dump([v.to_dict() for v in self._variables], f, indent=2)

    def _save_presets(self):
        with open(DATA_DIR / "presets.json", "w") as f:
            json.dump(self._presets, f, indent=2)

    def _save_hosts(self):
        with open(DATA_DIR / "hosts.json", "w") as f:
            json.dump({k: v.to_dict() for k, v in self._hosts.items()}, f, indent=2)

    def _save_history(self):
        with open(DATA_DIR / "history.json", "w") as f:
            json.dump(self._history[-5000:], f, indent=2)

    def get_workflow(self, wf_id: str) -> Optional[Workflow]:
        return self._workflows.get(wf_id)

    def get_all_workflows(self) -> list[dict]:
        return [wf.to_dict() for wf in self._workflows.values()]

    def get_workflow_statuses(self) -> list[dict]:
        return [{"id": wf.id, "name": wf.name, "state": wf.state.value} for wf in self._workflows.values()]

    def create_workflow(self, wf: Workflow) -> Workflow:
        self._workflows[wf.id] = wf
        self._save_workflow(wf)
        return wf

    def update_workflow(self, wf: Workflow) -> Workflow:
        self._workflows[wf.id] = wf
        self._save_workflow(wf)
        return wf

    def delete_workflow(self, wf_id: str):
        self._workflows.pop(wf_id, None)
        p = WORKFLOW_DIR / f"{wf_id}.json"
        if p.exists():
            p.unlink()

    def import_workflow(self, data: dict) -> Workflow:
        wf = Workflow.from_dict(data)
        self._workflows[wf.id] = wf
        self._save_workflow(wf)
        return wf

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_all_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    def get_running_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values() if j.state.value in ("queued", "running", "paused")]

    def create_job(self, job: Job) -> Job:
        self._jobs[job.id] = job
        self._save_job(job)
        return job

    def update_job(self, job: Job):
        self._jobs[job.id] = job
        self._save_job(job)

    def delete_job(self, job_id: str):
        self._jobs.pop(job_id, None)
        p = JOB_DIR / f"{job_id}.json"
        if p.exists():
            p.unlink()

    def get_history(self, start: int = 0, count: int = 250) -> list[dict]:
        return self._history[start:start + count]

    def add_history_entry(self, entry: dict):
        self._history.append(entry)
        self._save_history()

    def get_job_log(self, job_id: str, start: int = 0, count: int = 300) -> list[str]:
        job = self._jobs.get(job_id)
        if not job:
            return []
        lines = job.log_lines
        if count == 0:
            return lines[start:]
        return lines[start:start + count]

    def get_user_variables(self) -> list[dict]:
        return [v.to_dict() for v in self._variables]

    def set_user_variable(self, var: Variable):
        for i, v in enumerate(self._variables):
            if v.name == var.name:
                self._variables[i] = var
                self._save_variables()
                return
        self._variables.append(var)
        self._save_variables()

    def import_user_variable(self, data: dict) -> Variable:
        var = Variable.from_dict(data)
        self.set_user_variable(var)
        return var

    def get_presets(self) -> dict:
        return self._presets

    def set_preset(self, preset_id: str, data: dict):
        self._presets[preset_id] = data
        self._save_presets()

    def import_preset(self, preset_id: str, data: dict):
        self._presets[preset_id] = data
        self._save_presets()

    def register_host(self, host: HostInfo):
        self._hosts[host.name] = host
        self._save_hosts()

    def get_hosts(self) -> list[dict]:
        return [h.to_dict() for h in self._hosts.values()]

    def update_host(self, host_name: str, **kwargs):
        if host_name in self._hosts:
            for k, v in kwargs.items():
                setattr(self._hosts[host_name], k, v)
            self._hosts[host_name].last_seen = time.time()
            self._save_hosts()
