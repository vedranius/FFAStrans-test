"""Workflow execution engine - runs workflows through node graph.

Matches original FFAStrans execution model:
- Find start node (monitor or specified)
- Execute nodes sequentially through connections
- Handle success/error paths
- Set job variables from node execution
- Track split progress
"""
import os
import platform
import time
import logging
import threading
import json
from typing import Optional
from .models import (
    Workflow, Job, Node, NodeState, JobState, WorkflowState,
    SplitInfo, Variable, ConditionExpression
)
from .storage import Storage
from .variables import VariableEngine
from ..nodes.registry import create_node_instance, get_node_class

logger = logging.getLogger('ffastrans.engine')


class WorkflowEngine:
    def __init__(self, storage: Storage):
        self.storage = storage
        self._running: dict[str, bool] = {}
        self._threads: dict[str, threading.Thread] = {}

    def _find_start_node(self, wf: Workflow, start_proc: str = '') -> Optional[Node]:
        if start_proc:
            for node in wf.nodes:
                n = node if isinstance(node, dict) else node
                nid = n.get('id') if isinstance(n, dict) else n.id
                nname = n.get('name') if isinstance(n, dict) else n.name
                if nid == start_proc or nname == start_proc:
                    if isinstance(n, dict):
                        return Node.from_dict(n)
                    return n

        for node in wf.nodes:
            n = node if isinstance(node, dict) else node
            ntype = n.get('node_type') if isinstance(n, dict) else n.node_type
            if ntype.startswith('mon_'):
                if isinstance(n, dict):
                    return Node.from_dict(n)
                return n

        nodes = wf.nodes
        if nodes:
            n = nodes[0]
            if isinstance(n, dict):
                return Node.from_dict(n)
            return n
        return None

    def _find_next_nodes(self, wf: Workflow, current_node_id: str, success: bool) -> list[Node]:
        next_nodes = []
        for conn in wf.connections:
            c = conn if isinstance(conn, dict) else conn
            from_node = c.get('from_node') if isinstance(c, dict) else c.from_node
            from_port = c.get('from_port') if isinstance(c, dict) else c.from_port
            to_node = c.get('to_node') if isinstance(c, dict) else c.to_node

            if from_node == current_node_id:
                if (success and from_port == 'output') or (not success and from_port == 'error'):
                    for node in wf.nodes:
                        n = node if isinstance(node, dict) else node
                        nid = n.get('id') if isinstance(n, dict) else n.id
                        if nid == to_node:
                            if isinstance(n, dict):
                                next_nodes.append(Node.from_dict(n))
                            else:
                                next_nodes.append(n)
        return next_nodes

    def _build_var_engine(self, wf: Workflow, job: Job) -> VariableEngine:
        user_vars = {}
        for v in self.storage.get_user_variables():
            name = v.get('name', '')
            val = v.get('value', '')
            prefix = v.get('vtype', 's')
            user_vars[name] = val

        workflow_vars = {}
        for v in wf.variables:
            var = v if isinstance(v, dict) else v.to_dict()
            name = var.get('name', '')
            val = var.get('value', '')
            workflow_vars[name] = val

        return VariableEngine(
            user_vars=user_vars,
            job_vars=dict(job.variables),
            workflow_vars=workflow_vars,
        )

    def _populate_file_vars(self, var_engine: VariableEngine, job: Job):
        if job.input_file:
            from pathlib import Path
            p = Path(job.input_file)
            var_engine.set_job_var('s_source', str(p))
            var_engine.set_job_var('s_original_full', str(p))
            var_engine.set_job_var('s_original_name', p.name)
            var_engine.set_job_var('s_original_ext', p.suffix)
            var_engine.set_job_var('s_original_path', str(p.parent))
            var_engine.set_job_var('f_fsize', str(p.stat().st_size) if p.exists() else '0')

    def run_job(self, job: Job):
        wf = self.storage.get_workflow(job.wf_id)
        if not wf:
            job.state = JobState.FAILED
            job.error = f'Workflow not found: {job.wf_id}'
            self.storage.update_job(job)
            return

        var_engine = self._build_var_engine(wf, job)
        self._populate_file_vars(var_engine, job)

        var_engine.set_job_var('s_wf_name', wf.name)
        var_engine.set_job_var('s_wf_id', wf.id)
        var_engine.set_job_var('s_job_id', job.id)
        var_engine.set_job_var('s_hostname', platform.node())

        start_node = self._find_start_node(wf, job.start_proc)

        if not start_node:
            job.state = JobState.FAILED
            job.error = 'No start node found'
            self.storage.update_job(job)
            return

        split = SplitInfo(
            current_node=start_node.id,
            state=JobState.RUNNING,
            started_at=time.time(),
        )
        job.splits = [split]
        job.state = JobState.RUNNING
        job.started_at = time.time()
        self.storage.update_job(job)

        logger.info(f'Starting job {job.id} on workflow {wf.name}')
        current_nodes = [start_node]

        while current_nodes and self._running.get(job.id, False) is not False:
            next_nodes = []
            for current in current_nodes:
                if not self._running.get(job.id, True):
                    break

                var_engine.set_job_var('s_node_name', current.name)
                var_engine.set_job_var('s_node_id', current.id)

                node_instance = create_node_instance(current, job, var_engine)
                if not node_instance:
                    logger.warning(f'No node class for type: {current.node_type}')
                    split.state = JobState.FAILED
                    split.error = f'Unknown node type: {current.node_type}'
                    job.state = JobState.FAILED
                    job.error = split.error
                    self.storage.update_job(job)
                    return

                split.current_node = current.id
                self.storage.update_job(job)

                success = node_instance.run()
                if success:
                    split.state = JobState.COMPLETED
                    split.progress = 100.0
                    next_nodes.extend(self._find_next_nodes(wf, current.id, True))
                else:
                    split.state = JobState.FAILED
                    split.error = job.error
                    next_nodes.extend(self._find_next_nodes(wf, current.id, False))

                for s in job.splits:
                    if isinstance(s, dict):
                        if s.get('split_id') == split.split_id:
                            s['state'] = split.state.value
                            s['progress'] = split.progress
                            s['error'] = split.error
                    else:
                        if s.split_id == split.split_id:
                            s.state = split.state
                            s.progress = split.progress
                            s.error = split.error

            current_nodes = next_nodes

        job.finished_at = time.time()
        if self._running.get(job.id) is not False:
            has_failed = False
            for s in job.splits:
                state_val = s.get('state') if isinstance(s, dict) else s.state.value
                if state_val == 'failed':
                    has_failed = True
                    break
            job.state = JobState.FAILED if has_failed else JobState.COMPLETED
        else:
            job.state = JobState.ABORTED

        split.finished_at = time.time()
        self._pop_job(job.id)
        self.storage.update_job(job)

        self.storage.add_history_entry({
            'job_id': job.id,
            'wf_id': job.wf_id,
            'wf_name': wf.name,
            'input_file': job.input_file,
            'output_file': job.variables.get('s_output_file', ''),
            'state': job.state.value,
            'started_at': job.started_at,
            'finished_at': job.finished_at,
            'host': job.host,
            'error': job.error,
        })

        logger.info(f'Job {job.id} finished with state: {job.state.value}')

    def start_job(self, job: Job):
        self._running[job.id] = True
        t = threading.Thread(target=self.run_job, args=(job,), daemon=True)
        self._threads[job.id] = t
        t.start()

    def abort_job(self, job_id: str):
        self._running[job_id] = False
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.ABORTED
            self.storage.update_job(job)

    def _pop_job(self, job_id: str):
        self._running.pop(job_id, None)
        self._threads.pop(job_id, None)

    def pause_job(self, job_id: str, split_id: str = ''):
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.PAUSED
            for s in job.splits:
                sid = s.get('split_id') if isinstance(s, dict) else s.split_id
                if not split_id or sid == split_id:
                    if isinstance(s, dict):
                        s['state'] = 'paused'
                    else:
                        s.state = JobState.PAUSED
            self.storage.update_job(job)

    def resume_job(self, job_id: str, split_id: str = ''):
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.RUNNING
            for s in job.splits:
                sid = s.get('split_id') if isinstance(s, dict) else s.split_id
                if not split_id or sid == split_id:
                    if isinstance(s, dict):
                        s['state'] = 'running'
                    else:
                        s.state = JobState.RUNNING
            self.storage.update_job(job)

    def retry_job(self, job_id: str):
        job = self.storage.get_job(job_id)
        if job:
            job.state = JobState.QUEUED
            job.error = ''
            job.started_at = 0.0
            job.finished_at = 0.0
            self.storage.update_job(job)
            self.start_job(job)
