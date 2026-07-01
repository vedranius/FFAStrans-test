"""Data models for workflows, jobs, nodes, and variables."""
import uuid
import time
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Optional


class NodeState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"
    PAUSED = "paused"


class WorkflowState(str, Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    DISABLED = "disabled"


class MonitorType(str, Enum):
    FOLDER = "mon_folder"
    FTP = "mon_ftp"
    SEQUENCE = "mon_sequence"
    P2 = "mon_p2"
    XF = "mon_xf"
    GOPRO = "mon_gopro"


class EncoderType(str, Enum):
    H265 = "enc_av_265"
    H264_MP4 = "enc_av_mp4"
    PRORES = "enc_av_prores"
    DNXHR = "enc_av_dnxhr"
    DNxHD = "enc_av_dnxhd"
    XDCAMHD = "enc_av_xdcamhd"
    AVCINTRA = "enc_av_avcintra"
    AV1 = "enc_av_av1"
    MPEG = "enc_av_mpeg"
    UNCOMPRESSED = "enc_av_uncomp"
    AUDIO = "enc_a_audio"
    CUSTOM_FFMPEG = "enc_av_customff"


class FilterType(str, Enum):
    RESIZE = "avs_v_resize"
    CROP = "avs_v_crop"
    COLOR = "avs_v_color"
    WATERMARK = "avs_v_watermark"
    TIMECODE = "avs_v_tc"
    DEINTERLACE = "avs_v_deinterlace"
    PAD = "avs_v_pad"
    FLIP = "avs_v_flip"
    REVERSE = "avs_v_reverse"
    FPS = "avs_v_fpsconv"
    LINEAR_TRANS = "avs_v_linear_trans"
    SAFECOLOR = "avs_v_safecolorlimiter"
    SWAPFIELDS = "avs_v_swapfields"
    VIDEOLAYER = "avs_v_videolayer"
    FADE = "avs_av_fade"
    INSERTMEDIA = "avs_av_insertmedia"


class DecoderType(str, Enum):
    MEDIA = "dec_avmedia"
    STILLS = "dec_stills"
    YOUTUBE = "dec_youtube"


class OperatorType(str, Enum):
    CONDITION = "op_cond"
    FOREACH = "op_foreach"
    HOLD = "op_hold"
    POPULATE = "op_populate"
    ANALYZER = "op_analyzer"


class DestinationType(str, Enum):
    FOLDER = "dest_folder"
    FTP = "dest_ftp"
    MEDIA_DIST = "dest_mediadist"


class OtherNodeType(str, Enum):
    EMAIL = "other_email"
    HTTPSEND = "other_httpsend"
    TEXTFILE = "other_textfile"
    CMD_RUN = "cmd_run"


@dataclass
class Variable:
    name: str
    vtype: str = "s"
    value: Any = ""
    is_static: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Node:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    node_type: str = ""
    params: dict = field(default_factory=dict)
    x: float = 0
    y: float = 0
    state: NodeState = NodeState.IDLE
    preset_id: Optional[str] = None
    on_success: Optional[str] = None
    on_failure: Optional[str] = None

    def to_dict(self):
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        if "state" in d:
            d["state"] = NodeState(d["state"])
        return cls(**d)


@dataclass
class Connection:
    from_node: str = ""
    from_port: str = "output"
    to_node: str = ""
    to_port: str = "input"

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Workflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Workflow"
    nodes: list = field(default_factory=list)
    connections: list = field(default_factory=list)
    variables: list = field(default_factory=list)
    state: WorkflowState = WorkflowState.STOPPED
    drop_folders: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self):
        d = {
            "id": self.id,
            "name": self.name,
            "nodes": [n.to_dict() if hasattr(n, "to_dict") else n for n in self.nodes],
            "connections": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.connections],
            "variables": [v.to_dict() if hasattr(v, "to_dict") else v for v in self.variables],
            "state": self.state.value,
            "drop_folders": self.drop_folders,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        nodes = [Node.from_dict(n) if isinstance(n, dict) else n for n in d.pop("nodes", [])]
        connections = [Connection.from_dict(c) if isinstance(c, dict) else c for c in d.pop("connections", [])]
        variables = [Variable.from_dict(v) if isinstance(v, dict) else v for v in d.pop("variables", [])]
        if "state" in d:
            d["state"] = WorkflowState(d["state"])
        wf = cls(**d)
        wf.nodes = nodes
        wf.connections = connections
        wf.variables = variables
        return wf


@dataclass
class SplitInfo:
    split_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    current_node: str = ""
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""

    def to_dict(self):
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        if "state" in d:
            d["state"] = JobState(d["state"])
        return cls(**d)


@dataclass
class Job:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    wf_id: str = ""
    input_file: str = ""
    start_proc: str = ""
    priority: int = 2
    state: JobState = JobState.QUEUED
    variables: dict = field(default_factory=dict)
    splits: list = field(default_factory=list)
    host: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    error: str = ""
    log_lines: list = field(default_factory=list)
    total_progress: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "id": self.id,
            "wf_id": self.wf_id,
            "input_file": self.input_file,
            "start_proc": self.start_proc,
            "priority": self.priority,
            "state": self.state.value,
            "variables": self.variables,
            "splits": [s.to_dict() if hasattr(s, "to_dict") else s for s in self.splits],
            "host": self.host,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "log_lines": self.log_lines[-300:],
            "total_progress": self.total_progress,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        splits = [SplitInfo.from_dict(s) if isinstance(s, dict) else s for s in d.pop("splits", [])]
        if "state" in d:
            d["state"] = JobState(d["state"])
        job = cls(**d)
        job.splits = splits
        return job


@dataclass
class HostInfo:
    name: str = ""
    hostname: str = ""
    ip: str = ""
    port: int = 8080
    groups: list = field(default_factory=list)
    max_jobs: int = 4
    current_jobs: int = 0
    active: bool = True
    last_seen: float = 0.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)
