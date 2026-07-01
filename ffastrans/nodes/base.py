"""Base class for all processor nodes."""
import subprocess
import logging
import time
import os
from abc import ABC, abstractmethod
from ..core.models import Node, Job, NodeState, JobState
from ..core.variables import VariableEngine

logger = logging.getLogger("ffastrans.nodes")


class BaseNode(ABC):
    node_type = "base"

    def __init__(self, node: Node, job: Job, var_engine: VariableEngine):
        self.node = node
        self.job = job
        self.var_engine = var_engine
        self.logger = logging.getLogger(f"ffastrans.nodes.{node.id}")

    def resolve(self, text) -> str:
        return self.var_engine.resolve(str(text))

    def log(self, message: str):
        line = f"[{self.node.name}] {message}"
        self.logger.info(message)
        self.job.log_lines.append(line)

    def run_command(self, cmd: list[str], timeout: int = 3600) -> tuple[int, str, str]:
        resolved = [self.resolve(c) for c in cmd]
        self.log(f"Executing: {' '.join(resolved)}")
        try:
            result = subprocess.run(
                resolved,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy(),
            )
            if result.stdout:
                for line in result.stdout.strip().split("\n")[-50:]:
                    self.job.log_lines.append(f"[stdout] {line}")
            if result.stderr:
                for line in result.stderr.strip().split("\n")[-50:]:
                    self.job.log_lines.append(f"[stderr] {line}")
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log("Command timed out")
            return 1, "", "Timeout expired"
        except FileNotFoundError as e:
            self.log(f"Command not found: {e}")
            return 1, "", str(e)
        except Exception as e:
            self.log(f"Command error: {e}")
            return 1, "", str(e)

    @abstractmethod
    def execute(self) -> bool:
        pass

    def run(self) -> bool:
        self.node.state = NodeState.RUNNING
        self.job.state = JobState.RUNNING
        self.job.host = os.uname().nodename
        self.job.started_at = time.time()
        try:
            success = self.execute()
            self.node.state = NodeState.COMPLETED if success else NodeState.FAILED
            return success
        except Exception as e:
            self.log(f"Node execution error: {e}")
            self.node.state = NodeState.FAILED
            self.job.error = str(e)
            return False
