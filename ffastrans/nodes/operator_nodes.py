"""Operator, destination, and utility nodes."""
import os
import json
import logging
import subprocess
import smtplib
import urllib.request
from pathlib import Path
from email.mime.text import MIMEText
from .base import BaseNode
from ..core.config import FFMPEG_PATH
from ..core.models import NodeState, JobState

logger = logging.getLogger("ffastrans.nodes.operators")


class ConditionNode(BaseNode):
    node_type = "op_cond"

    def execute(self) -> bool:
        params = self.node.params
        var_name = self.resolve(params.get("variable", ""))
        condition = params.get("condition", "equals")
        compare_val = self.resolve(params.get("value", ""))

        actual_val = self.var_engine.job_vars.get(var_name, self.var_engine.user_vars.get(var_name, ""))

        result = False
        if condition == "equals":
            result = str(actual_val) == str(compare_val)
        elif condition == "not_equals":
            result = str(actual_val) != str(compare_val)
        elif condition == "contains":
            result = str(compare_val) in str(actual_val)
        elif condition == "gt":
            try:
                result = float(actual_val) > float(compare_val)
            except ValueError:
                result = False
        elif condition == "lt":
            try:
                result = float(actual_val) < float(compare_val)
            except ValueError:
                result = False
        elif condition == "exists":
            result = var_name in self.var_engine.job_vars or var_name in self.var_engine.user_vars

        self.log(f"Condition: {var_name} {condition} {compare_val} = {result}")
        if result:
            self.node.state = NodeState.COMPLETED
        else:
            self.node.state = NodeState.SKIPPED
        return result


class PopulateNode(BaseNode):
    node_type = "op_populate"

    def execute(self) -> bool:
        params = self.node.params
        template = self.resolve(params.get("template", ""))
        output_path = self.resolve(params.get("output_path", ""))

        if not template:
            self.log("No template specified")
            return False

        self.log(f"Populating template -> {output_path}")
        try:
            result = self.var_engine.resolve(template)
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w") as f:
                    f.write(result)
                self.job.variables["s_output_file"] = output_path
            else:
                self.job.variables["s_populated_text"] = result
            return True
        except Exception as e:
            self.log(f"Populate failed: {e}")
            return False


class AnalyzeNode(BaseNode):
    node_type = "op_analyzer"

    def execute(self) -> bool:
        input_file = self.resolve(self.node.params.get("input", self.job.input_file))
        if not input_file or not Path(input_file).exists():
            self.log(f"File not found: {input_file}")
            return False

        self.log(f"Analyzing: {input_file}")
        stat = Path(input_file).stat()
        self.job.variables["i_file_size"] = str(stat.st_size)
        self.job.variables["s_file_name"] = Path(input_file).name
        self.job.variables["s_file_ext"] = Path(input_file).suffix
        self.job.variables["s_file_dir"] = str(Path(input_file).parent)
        return True


class ForeachNode(BaseNode):
    node_type = "op_foreach"

    def execute(self) -> bool:
        var_name = self.node.params.get("variable", "s_item")
        items_str = self.resolve(self.node.params.get("items", ""))
        items = [i.strip() for i in items_str.split(",") if i.strip()]
        self.log(f"Foreach: {len(items)} items")
        for item in items:
            self.var_engine.job_vars[var_name] = item
            self.log(f"  Item: {item}")
        return True


class HoldNode(BaseNode):
    node_type = "op_hold"

    def execute(self) -> bool:
        seconds = int(self.node.params.get("seconds", "5"))
        self.log(f"Holding for {seconds} seconds")
        import time
        time.sleep(seconds)
        return True


class CMDRunNode(BaseNode):
    node_type = "cmd_run"

    def execute(self) -> bool:
        command = self.resolve(self.node.params.get("command", ""))
        if not command:
            self.log("No command specified")
            return False

        self.log(f"Running command: {command}")
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=300
            )
            self.job.variables["i_exit_code"] = str(result.returncode)
            self.job.variables["s_stdout"] = result.stdout[-4000:]
            self.job.variables["s_stderr"] = result.stderr[-4000:]
            self.log(f"Exit code: {result.returncode}")
            return result.returncode == 0
        except Exception as e:
            self.log(f"Command error: {e}")
            return False


class EmailNode(BaseNode):
    node_type = "other_email"

    def execute(self) -> bool:
        params = self.node.params
        smtp_server = self.resolve(params.get("smtp_server", ""))
        smtp_port = int(params.get("smtp_port", "587"))
        sender = self.resolve(params.get("from", ""))
        recipient = self.resolve(params.get("to", ""))
        subject = self.resolve(params.get("subject", "FFAStrans notification"))
        body = self.resolve(params.get("body", ""))
        use_tls = params.get("tls", True)

        if not all([smtp_server, sender, recipient]):
            self.log("Missing email configuration")
            return False

        self.log(f"Sending email to: {recipient}")
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = recipient

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.send_message(msg)
            self.log("Email sent successfully")
            return True
        except Exception as e:
            self.log(f"Email failed: {e}")
            return False


class HTTPSendNode(BaseNode):
    node_type = "other_httpsend"

    def execute(self) -> bool:
        params = self.node.params
        url = self.resolve(params.get("url", ""))
        method = params.get("method", "GET")
        body = self.resolve(params.get("body", ""))

        if not url:
            self.log("No URL specified")
            return False

        self.log(f"HTTP {method}: {url}")
        try:
            data = body.encode("utf-8") if body else None
            req = urllib.request.Request(url, data=data, method=method)
            if body:
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = resp.read().decode("utf-8")
                self.job.variables["s_http_response"] = resp_data
                self.job.variables["i_http_status"] = str(resp.status)
                self.log(f"HTTP response: {resp.status}")
                return True
        except Exception as e:
            self.log(f"HTTP error: {e}")
            return False


class TextFileNode(BaseNode):
    node_type = "other_textfile"

    def execute(self) -> bool:
        params = self.node.params
        content = self.resolve(params.get("content", ""))
        output_path = self.resolve(params.get("output_path", ""))

        if not output_path:
            self.log("No output path specified")
            return False

        self.log(f"Writing text file: {output_path}")
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(content)
            self.job.variables["s_output_file"] = output_path
            return True
        except Exception as e:
            self.log(f"File write error: {e}")
            return False


class FolderDestination(BaseNode):
    node_type = "dest_folder"

    def execute(self) -> bool:
        input_file = self.resolve(self.node.params.get("input", self.job.input_file))
        output_dir = self.resolve(self.node.params.get("path", os.getenv("FFASTRANS_OUTPUT_DIR", "drop_folders/output")))
        rename = self.resolve(self.node.params.get("rename", ""))

        if not input_file or not Path(input_file).exists():
            self.log(f"Input file not found: {input_file}")
            return False

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        if rename:
            output_path = str(Path(output_dir) / rename)
        else:
            output_path = str(Path(output_dir) / Path(input_file).name)

        self.log(f"Copying to: {output_path}")
        import shutil
        try:
            shutil.copy2(input_file, output_path)
            self.job.variables["s_output_file"] = output_path
            self.log("Copy complete")
            return True
        except Exception as e:
            self.log(f"Copy failed: {e}")
            return False


OPERATOR_NODES = {
    "op_cond": ConditionNode,
    "op_populate": PopulateNode,
    "op_analyzer": AnalyzeNode,
    "op_foreach": ForeachNode,
    "op_hold": HoldNode,
    "cmd_run": CMDRunNode,
    "other_email": EmailNode,
    "other_httpsend": HTTPSendNode,
    "other_textfile": TextFileNode,
    "dest_folder": FolderDestination,
}
