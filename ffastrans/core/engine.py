"""Workflow execution engine - runs workflows through node graph."""
import os
import time
import logging
from typing import Optional
from .models import Workflow, Job, Node, NodeState, JobState, WorkflowState, SplitInfo, Variable
from .storage import Storage
from .variables import VariableEngine
from ..nodes.registry import create_node_instance, get_node_class

logger = logging.getLogger("ffastrans.engine")


class WorkflowEngine:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._running: dict[str, bool] = {}

    def _find_start_node(self, wf: Workflow, start_proc: str = "") -> Optional[Node]:
        if start_proc:
            for node in wf.nodes:
                n = node if isinstance(node, dict) else node.to_dict()
                if n.get("id") == start_proc or n.get("name") == start_proc:
                    return node if not isinstance(node, dict) else Node.from_dict(node)

        for node in wf.nodes:
            n = node if isinstance(node, dict) else node.to_dict()
            ntype = n.get("node_type", "")
            if ntype.startswith("mon_"):
                return node if not isinstance(node, dict) else Node.from_dict(node)

        nodes = wf.nodes
        if nodes:
            return nodes[0] if not isinstance(nodes[0], dict) else Node.from_dict(nodes[0])
        return None

    def _find_next_nodes(self, wf: Workflow, current_node_id: str, success: bool) -> list[Node]:
        next_nodes = []
        for conn in wf.connections:
            c = conn if isinstance(conn, dict) else conn.to_dict()
            if c.get("from_node") == current_node_id:
                port = c.get("from_port", "output")
                if (success and port == "output") or (not success and port == "error"):
                    to_node_id = c.get("to_node")
                    for node in wf.nodes:
                        n = node if isinstance(node, dict) else node.to_dict()
                        if n.get("id") == to_node_id:
                            next_nodes.append(node if not isinstance(node, dict) else Node.from_dict(node))
        return next_nodes

    def _build_var_engine(self, wf: Workflow, job: Job) -> VariableEngine:
        user_vars = {}
        for v in wf.variables:
            var = v if isinstance(v, dict) else v.to_dict()
            name = var.get("name", "")
            val = var.get("value", "")
            user_vars[name] = val

        for sv in self.storage.get_user_variables():
            user_vars[sv["name"]] = sv.get("value", "")

        return VariableEngine(user_vars=user_vars, job_vars=dict(job.variables))

    def run_job(self, job: Job):
        wf = self.storage.get_workflow(job.wf_id)
        if not wf:
            job.state = JobState.FAILED
            job.error = f"Workflow not found: {job.wf_id}"
            self.storage.update_job(job)
            return

        var_engine = self._build_var_engine(wf, job)
        start_node = self._find_start_node(wf, job.start_proc)

        if not start_node:
            job.state = JobState.FAILED
            job.error = "No start node found"
            self.storage.update_job(job)
            return

        split = SplitInfo(
            current_node=start_node.id if isinstance(start_node, dict) else start_node.id,
            state=JobState.RUNNING,
            started_at=time.time(),
        )
        job.splits = [split]
        job.state = JobState.RUNNING
        job.started_at = time.time()
        self.storage.update_job(job)

        logger.info(f"Starting job {job.id} on workflow {wf.name}")
        current_nodes = [start_node]

        while current_nodes and self._running.get(job.id, False) is not False:
            next_nodes = []
            for current in current_nodes:
                if not self._running.get(job.id, True):
                    break

                node_instance = create_node_instance(current, job, var_engine)
                if not node_instance:
                    logger.warning(f"No node class for type: {current.node_type if isinstance(current, dict) else current.node_type}")
                    split.state = JobState.FAILED
                    split.error = f"Unknown node type: {current.node_type}"
                    job.state = JobState.FAILED
                    self.storage.update_job(job)
                    return

                split.current_node = current.id if isinstance(current, dict) else current.id
                self.storage.update_job(job)

                success = node_instance.run()
                if success:
                    split.state = JobState.COMPLETED
                    split.progress = 100.0
                    next_nodes.extend(self._find_next_nodes(wf, current.id if isinstance(current, dict) else current.id, True))
                else:
                    split.state = JobState.FAILED
                    split.error = job.error
                    next_nodes.extend(self._find_next_nodes(wf, current.id if isinstance(current, dict) else current.id, False))

            current_nodes = next_nodes

        job.finished_at = time.time()
        if self._running.get(job.id) is not False:
            has_failed = any(
                (s.get("state") if isinstance(s, dict) else s.state.value) == "failed"
                for s in job.splits
            )
            if has_failed:
                job.state = JobState.FAILED
            else:
                job.state = JobState.COMPLETED
        else:
            job.state = JobState.ABORTED

        split.finished_at = time.time()
        self._pop_job(job.id)
        self.storage.update_job(job)

        self.storage.add_history_entry({
            "job_id": job.id,
            "wf_id": job.wf_id,
            "wf_name": wf.name,
            "input_file": job.input_file,
            "state": job.state.value,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "host": job.host,
            "error": job.error,
        })

        logger.info(f"Job {job.id} finished with state: {job.state.value}")

    def start_job(self, job: Job):
        self._running[job.id] = True
        import threading
        t = threading.Thread(target=self.run_job, args=(job,), daemon=True)
        t.start()

    def abort_job(self, job_id: str):
        self._running[job_id] = False
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.ABORTED
            self.storage.update_job(job)

    def _pop_job(self, job_id: str):
        self._running.pop(job_id, None)

    def pause_job(self, job_id: str, split_id: str = ""):
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.PAUSED
            for s in job.splits:
                sid = s.split_id if isinstance(s, dict) else s.get("split_id", "")
                if not split_id or sid == split_id:
                    if isinstance(s, dict):
                        s["state"] = "paused"
                    else:
                        s.state = JobState.PAUSED
            self.storage.update_job(job)

    def resume_job(self, job_id: str, split_id: str = ""):
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.RUNNING
            self.storage.update_job(job)
