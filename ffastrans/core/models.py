"""Data models for workflows, jobs, nodes, and variables.

Matches original FFAStrans data structures:
- Workflow properties: sleep_timer, cron, priority (0-5), timeout_level, active_on
- Condition node: 8 expression rows with And/Or logic
- Populate node: 8 variable assignment rows
- Node presets system
"""
import uuid
import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class NodeState(str, Enum):
    IDLE = 'idle'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    SKIPPED = 'skipped'
    PAUSED = 'paused'


class JobState(str, Enum):
    QUEUED = 'queued'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ABORTED = 'aborted'
    PAUSED = 'paused'


class WorkflowState(str, Enum):
    STOPPED = 'stopped'
    RUNNING = 'running'
    DISABLED = 'disabled'


@dataclass
class Variable:
    name: str
    vtype: str = 's'
    value: Any = ''
    is_static: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Node:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ''
    node_type: str = ''
    params: dict = field(default_factory=dict)
    x: float = 0
    y: float = 0
    state: NodeState = NodeState.IDLE
    preset_id: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d['state'] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        if 'state' in d:
            d['state'] = NodeState(d['state'])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Connection:
    from_node: str = ''
    from_port: str = 'output'
    to_node: str = ''
    to_port: str = 'input'

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ConditionExpression:
    expression_row: int = 0
    variable: str = ''
    operator: str = '='
    value: str = ''
    and_or: str = ''
    dispel_on_false: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PopulateExpression:
    populate_row: int = 0
    variable: str = ''
    value: str = ''

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Workflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = 'New Workflow'
    description: str = ''
    nodes: list = field(default_factory=list)
    connections: list = field(default_factory=list)
    variables: list = field(default_factory=list)
    drop_folders: list = field(default_factory=list)
    state: WorkflowState = WorkflowState.STOPPED

    work_folder: str = ''
    sleep_timer: int = 10
    cron: str = ''
    priority: int = 2
    timeout_level: int = 3
    active_on: list = field(default_factory=lambda: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'])

    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        d = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'nodes': [n.to_dict() if hasattr(n, 'to_dict') else n for n in self.nodes],
            'connections': [c.to_dict() if hasattr(c, 'to_dict') else c for c in self.connections],
            'variables': [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.variables],
            'drop_folders': self.drop_folders,
            'state': self.state.value,
            'work_folder': self.work_folder,
            'sleep_timer': self.sleep_timer,
            'cron': self.cron,
            'priority': self.priority,
            'timeout_level': self.timeout_level,
            'active_on': self.active_on,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        nodes = [Node.from_dict(n) if isinstance(n, dict) else n for n in d.pop('nodes', [])]
        connections = [Connection.from_dict(c) if isinstance(c, dict) else c for c in d.pop('connections', [])]
        variables = [Variable.from_dict(v) if isinstance(v, dict) else v for v in d.pop('variables', [])]
        if 'state' in d:
            d['state'] = WorkflowState(d['state'])
        filtered = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        wf = cls(**filtered)
        wf.nodes = nodes
        wf.connections = connections
        wf.variables = variables
        return wf


@dataclass
class SplitInfo:
    split_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    current_node: str = ''
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ''

    def to_dict(self):
        d = asdict(self)
        d['state'] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        if 'state' in d:
            d['state'] = JobState(d['state'])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    wf_id: str = ''
    input_file: str = ''
    start_proc: str = ''
    priority: int = 2
    state: JobState = JobState.QUEUED
    variables: dict = field(default_factory=dict)
    splits: list = field(default_factory=list)
    host: str = ''
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ''
    log_lines: list = field(default_factory=list)
    total_progress: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            'id': self.id,
            'wf_id': self.wf_id,
            'input_file': self.input_file,
            'start_proc': self.start_proc,
            'priority': self.priority,
            'state': self.state.value,
            'variables': self.variables,
            'splits': [s.to_dict() if hasattr(s, 'to_dict') else s for s in self.splits],
            'host': self.host,
            'started_at': self.started_at,
            'finished_at': self.finished_at,
            'error': self.error,
            'log_lines': self.log_lines[-300:],
            'total_progress': self.total_progress,
            'created_at': self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        splits = [SplitInfo.from_dict(s) if isinstance(s, dict) else s for s in d.pop('splits', [])]
        if 'state' in d:
            d['state'] = JobState(d['state'])
        filtered = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        job = cls(**filtered)
        job.splits = splits
        return job


@dataclass
class HostInfo:
    name: str = ''
    hostname: str = ''
    ip: str = ''
    port: int = 8080
    groups: list = field(default_factory=list)
    max_jobs_per_class: dict = field(default_factory=lambda: {
        '0': 2, '1': 2, '2': 2, '3': 2, '4': 2, '5': 2
    })
    cpu_roof: int = 20
    current_jobs: int = 0
    active: bool = True
    passive: bool = False
    last_seen: float = 0.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
