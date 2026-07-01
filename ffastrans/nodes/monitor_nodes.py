"""Folder and file monitor nodes - watches for new files."""
import os
import time
import hashlib
import json
import logging
from pathlib import Path
from .base import BaseNode
from ..core.models import NodeState

logger = logging.getLogger("ffastrans.nodes.monitor")


class FolderMonitor(BaseNode):
    node_type = "mon_folder"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_file = Path(os.getenv("FFASTRANS_DATA_DIR", "data")) / f"monitor_{self.node.id}.json"

    def _load_state(self) -> dict:
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {"seen_files": []}

    def _save_state(self, state: dict):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f)

    def execute(self) -> bool:
        params = self.node.params
        monitor_path = self.resolve(params.get("path", ""))
        watch_mode = params.get("mode", "new")
        file_filter = params.get("filter", "*.*")
        recursive = params.get("recursive", False)
        poll_interval = int(params.get("poll_interval", "2"))

        self.log(f"Starting folder monitor on: {monitor_path}")

        monitor_dir = Path(monitor_path)
        if not monitor_dir.exists():
            monitor_dir.mkdir(parents=True, exist_ok=True)
            self.log(f"Created monitor directory: {monitor_path}")

        state = self._load_state()
        seen = set(state.get("seen_files", []))

        pattern = f"**/{file_filter}" if recursive else file_filter

        while self.node.state == NodeState.RUNNING:
            try:
                current_files = set()
                for f in monitor_dir.glob(pattern):
                    if f.is_file():
                        current_files.add(str(f))

                new_files = current_files - seen
                if new_files:
                    self.log(f"Detected {len(new_files)} new file(s)")
                    state["seen_files"] = list(current_files)
                    self._save_state(state)
                    for f in sorted(new_files):
                        self.job.input_file = f
                        self.log(f"Processing: {f}")
                    return True

                if watch_mode == "once":
                    if not current_files:
                        self.log("No files found, exiting (once mode)")
                        return True
                    time.sleep(poll_interval)
                else:
                    time.sleep(poll_interval)

            except Exception as e:
                self.log(f"Monitor error: {e}")
                time.sleep(poll_interval)

        return True


class SequenceMonitor(BaseNode):
    node_type = "mon_sequence"

    def execute(self) -> bool:
        params = self.node.params
        seq_path = self.resolve(params.get("path", ""))
        seq_pattern = params.get("pattern", "%04d")
        seq_start = int(params.get("start", "0"))
        seq_end = int(params.get("end", "100"))
        seq_ext = params.get("extension", "dpx")

        self.log(f"Sequence monitor: {seq_path} ({seq_start}-{seq_end}.{seq_ext})")

        seq_dir = Path(seq_path)
        if not seq_dir.exists():
            self.log(f"Sequence directory not found: {seq_path}")
            return False

        frames = []
        for i in range(seq_start, seq_end + 1):
            frame = seq_dir / f"{seq_pattern.format(i)}.{seq_ext}"
            if frame.exists():
                frames.append(str(frame))

        if not frames:
            self.log("No frames found in sequence")
            return False

        self.job.variables["s_sequence_path"] = str(seq_dir)
        self.job.variables["s_sequence_first"] = frames[0]
        self.job.variables["s_sequence_last"] = frames[-1]
        self.job.variables["i_sequence_count"] = str(len(frames))
        self.job.input_file = frames[0]
        self.log(f"Sequence detected: {len(frames)} frames")
        return True


MONITOR_NODES = {
    "mon_folder": FolderMonitor,
    "mon_sequence": SequenceMonitor,
}
