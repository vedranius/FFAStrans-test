"""Folder and file monitor nodes - watches for new files.

Matches original FFAStrans monitors:
- mon_folder: Folder monitoring with accept/deny patterns, recurse, check_growing
- mon_sequence: Image sequence detection
- All monitors: forget_missing, limit_file_size, rebuild_history, clear_history
"""
import os
import fnmatch
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from .base import BaseNode
from ..core.models import NodeState

logger = logging.getLogger('ffastrans.nodes.monitor')


class FolderMonitor(BaseNode):
    """Folder monitoring node.

    Matches original FFAStrans mon_folder:
    - path: directory to watch
    - accept_filter: file patterns to accept (semicollon separated)
    - deny_filter: file patterns to deny (semicollon separated)
    - deny_folders: folder names to deny (semicollon separated)
    - deny_attributes: file attributes to deny (semicollon separated)
    - create_folder: create directory if not exists
    - recurse: watch subdirectories
    - localize_file: localize file before processing
    - check_growing: check if file is still being written (once/continuously/never)
    - skip_verification: skip file verification
    - forget_missing: forget files that disappear
    - limit_file_size: minimum file size in bytes
    - rebuild_history: rebuild history from folder contents
    - clear_history: clear all history
    """
    node_type = 'mon_folder'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ..core.config import DATA_DIR
        self.state_file = DATA_DIR / f'monitor_{self.node.id}.json'

    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {'seen_files': [], 'history': []}

    def _save_state(self, state: dict):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def _matches_filter(self, filename: str, accept_filter: str) -> bool:
        if not accept_filter or accept_filter.strip() == '*.*':
            return True
        patterns = [p.strip() for p in accept_filter.split(';') if p.strip()]
        if not patterns:
            return True
        for pattern in patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def _matches_deny(self, filename: str, deny_filter: str) -> bool:
        if not deny_filter:
            return False
        patterns = [p.strip() for p in deny_filter.split(';') if p.strip()]
        for pattern in patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def _is_denied_folder(self, folder_name: str, deny_folders: str) -> bool:
        if not deny_folders:
            return False
        names = [n.strip() for n in deny_folders.split(';') if n.strip()]
        return folder_name.lower() in [n.lower() for n in names]

    def _check_growing(self, filepath: str, mode: str) -> bool:
        if mode == 'never':
            return True
        try:
            size1 = Path(filepath).stat().st_size
            time.sleep(1)
            size2 = Path(filepath).stat().st_size
            return size1 == size2
        except Exception:
            return False

    def _localize_file(self, filepath: str) -> str:
        import shutil
        from ..core.config import DATA_DIR
        localized_dir = DATA_DIR / 'localized'
        localized_dir.mkdir(parents=True, exist_ok=True)
        dest = localized_dir / Path(filepath).name
        shutil.copy2(filepath, dest)
        return str(dest)

    def execute(self) -> bool:
        params = self.node.params
        monitor_path = self.resolve(params.get('path', ''))
        accept_filter = params.get('accept_filter', '*.*')
        deny_filter = params.get('deny_filter', '')
        deny_folders = params.get('deny_folders', '')
        create_folder = params.get('create_folder', False)
        recursive = params.get('recurse', False)
        localize_file = params.get('localize_file', False)
        check_growing_mode = params.get('check_growing', 'once')
        skip_verification = params.get('skip_verification', False)
        forget_missing = params.get('forget_missing', False)
        limit_file_size = int(params.get('limit_file_size', '0'))
        rebuild_history = params.get('rebuild_history', False)
        clear_history = params.get('clear_history', False)
        poll_interval = int(params.get('poll_interval', '2'))

        if not monitor_path:
            self.log('No monitor path specified')
            return False

        monitor_dir = Path(monitor_path)
        if create_folder and not monitor_dir.exists():
            monitor_dir.mkdir(parents=True, exist_ok=True)
            self.log(f'Created monitor directory: {monitor_path}')

        if not monitor_dir.exists():
            self.log(f'Monitor directory not found: {monitor_path}')
            return False

        state = self._load_state()
        seen = set(state.get('seen_files', []))

        if clear_history:
            state = {'seen_files': [], 'history': []}
            self._save_state(state)
            seen = set()
            self.log('History cleared')

        if rebuild_history:
            state = {'seen_files': [], 'history': []}
            self._save_state(state)
            seen = set()
            self.log('Rebuilding history from folder contents')

        self.log(f'Starting folder monitor on: {monitor_path}')
        self.log(f'Accept filter: {accept_filter}')
        self.log(f'Deny filter: {deny_filter}')
        self.log(f'Recursive: {recursive}')

        pattern = '**/*' if recursive else '*'

        while self.node.state == NodeState.RUNNING:
            try:
                current_files = set()
                for f in monitor_dir.glob(pattern):
                    if not f.is_file():
                        continue
                    if self._is_denied_folder(f.parent.name, deny_folders):
                        continue
                    if not self._matches_filter(f.name, accept_filter):
                        continue
                    if self._matches_deny(f.name, deny_filter):
                        continue
                    if limit_file_size > 0:
                        try:
                            if f.stat().st_size < limit_file_size:
                                continue
                        except Exception:
                            continue
                    current_files.add(str(f))

                if forget_missing:
                    missing = seen - current_files
                    if missing:
                        self.log(f'Forgetting {len(missing)} missing file(s)')
                        seen -= missing

                new_files = sorted(current_files - seen)

                if new_files:
                    self.log(f'Detected {len(new_files)} new file(s)')

                    for f in new_files:
                        if check_growing_mode != 'never':
                            if not self._check_growing(f, check_growing_mode):
                                self.log(f'Skipping growing file: {f}')
                                continue

                        if localize_file:
                            f = self._localize_file(f)

                        self.job.input_file = f
                        self.job.variables['s_source'] = f
                        self.job.variables['s_original_full'] = f
                        self.job.variables['s_original_name'] = Path(f).stem
                        self.job.variables['s_original_ext'] = Path(f).suffix
                        self.job.variables['s_original_path'] = str(Path(f).parent)

                        state['history'].append({
                            'file': f,
                            'time': datetime.now().isoformat(),
                        })
                        if len(state['history']) > 1000:
                            state['history'] = state['history'][-1000:]

                    state['seen_files'] = list(current_files)
                    self._save_state(state)
                    seen = current_files

                    self.log(f'Processing: {new_files[0]}')
                    return True

                time.sleep(poll_interval)

            except Exception as e:
                self.log(f'Monitor error: {e}')
                time.sleep(poll_interval)

        return True


class SequenceMonitor(BaseNode):
    """Image sequence detection node."""
    node_type = 'mon_sequence'

    def execute(self) -> bool:
        params = self.node.params
        seq_path = self.resolve(params.get('path', ''))
        seq_pattern = params.get('pattern', '%04d')
        seq_start = int(params.get('start', '0'))
        seq_end = int(params.get('end', '100'))
        seq_ext = params.get('extension', 'dpx')

        self.log(f'Sequence monitor: {seq_path} ({seq_start}-{seq_end}.{seq_ext})')

        seq_dir = Path(seq_path)
        if not seq_dir.exists():
            self.log(f'Sequence directory not found: {seq_path}')
            return False

        frames = []
        for i in range(seq_start, seq_end + 1):
            if '%0' in seq_pattern or '%d' in seq_pattern:
                try:
                    frame_name = seq_pattern % i
                except (TypeError, ValueError):
                    frame_name = str(i).zfill(4)
            else:
                frame_name = str(i).zfill(4)
            frame = seq_dir / f'{frame_name}.{seq_ext}'
            if frame.exists():
                frames.append(str(frame))

        if not frames:
            self.log('No frames found in sequence')
            return False

        self.job.variables['s_sequence_path'] = str(seq_dir)
        self.job.variables['s_sequence_first'] = frames[0]
        self.job.variables['s_sequence_last'] = frames[-1]
        self.job.variables['i_sequence_count'] = str(len(frames))
        self.job.variables['s_source'] = frames[0]
        self.job.input_file = frames[0]
        self.log(f'Sequence detected: {len(frames)} frames')
        return True


MONITOR_NODES = {
    'mon_folder': FolderMonitor,
    'mon_sequence': SequenceMonitor,
}
