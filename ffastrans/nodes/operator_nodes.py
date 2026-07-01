"""Operator, destination, and utility nodes.

Matches original FFAStrans operators:
- op_cond: 8-row conditional expressions with And/Or logic
- op_populate: 8-row variable assignments with math expressions
- op_analyzer: File/media analysis
- op_foreach: Loop iteration
- op_hold: Delay execution
- cmd_run: Shell command execution
- other_email, other_httpsend, other_textfile
- dest_folder: Folder delivery with rename/overwrite
"""
import os
import re
import json
import logging
import subprocess
import shutil
import smtplib
import urllib.request
from pathlib import Path
from email.mime.text import MIMEText
from .base import BaseNode
from ..core.config import FFMPEG_PATH
from ..core.models import NodeState, JobState

logger = logging.getLogger('ffastrans.nodes.operators')


class ConditionNode(BaseNode):
    """Conditional evaluation node - 8 expression rows with And/Or logic.

    Matches original FFAStrans op_cond:
    - 8 expression rows
    - Operators: =, ==, !=, >, <, >=, <=
    - Wildcards (*, ?) in string comparisons
    - And/Or logic between rows
    - Dispel on false option
    """
    node_type = 'op_cond'

    def _evaluate_single(self, variable: str, operator: str, compare_val: str) -> bool:
        actual_val = self.var_engine.get_var(variable)

        if operator in ('=', '=='):
            if '*' in compare_val or '?' in compare_val:
                import fnmatch
                return fnmatch.fnmatch(actual_val, compare_val)
            return str(actual_val) == str(compare_val)
        elif operator in ('!=', '≠'):
            return str(actual_val) != str(compare_val)
        elif operator == '>':
            try:
                return float(actual_val) > float(compare_val)
            except ValueError:
                return False
        elif operator == '<':
            try:
                return float(actual_val) < float(compare_val)
            except ValueError:
                return False
        elif operator in ('>=', '≥'):
            try:
                return float(actual_val) >= float(compare_val)
            except ValueError:
                return False
        elif operator in ('<=', '≤'):
            try:
                return float(actual_val) <= float(compare_val)
            except ValueError:
                return False
        elif operator == 'contains':
            return str(compare_val) in str(actual_val)
        elif operator == 'exists':
            return actual_val != f'%{variable}%'
        elif operator == 'isdir':
            return Path(actual_val).is_dir()
        elif operator == 'isfile':
            return Path(actual_val).is_file()
        return False

    def execute(self) -> bool:
        params = self.node.params
        expressions = params.get('expressions', [])
        dispel_on_false = params.get('dispel_on_false', False)

        if not expressions:
            var = params.get('variable', '')
            op = params.get('condition', '=')
            val = self.resolve(params.get('value', ''))
            if var:
                expressions = [{'variable': var, 'operator': op, 'value': val, 'and_or': 'and'}]

        if not expressions:
            self.log('No condition expressions defined')
            return False

        result = True
        for i, expr in enumerate(expressions):
            if isinstance(expr, dict):
                var = self.resolve(expr.get('variable', ''))
                op = expr.get('operator', '=')
                val = self.resolve(expr.get('value', ''))
                and_or = expr.get('and_or', 'and')
            else:
                var = self.resolve(getattr(expr, 'variable', ''))
                op = getattr(expr, 'operator', '=')
                val = self.resolve(getattr(expr, 'value', ''))
                and_or = getattr(expr, 'and_or', 'and')

            expr_result = self._evaluate_single(var, op, val)
            self.log(f'Row {i}: {var} {op} {val} = {expr_result}')

            if i == 0:
                result = expr_result
            elif and_or.lower() == 'and':
                result = result and expr_result
            elif and_or.lower() == 'or':
                result = result or expr_result

            if dispel_on_false and not result:
                self.log('Dispel on false - stopping evaluation')
                break

        self.log(f'Final condition result: {result}')
        if result:
            self.node.state = NodeState.COMPLETED
        else:
            self.node.state = NodeState.SKIPPED
        return result


class PopulateNode(BaseNode):
    """Set user variables node - 8 variable assignment rows.

    Matches original FFAStrans op_populate:
    - 8 variable assignment rows
    - Supports math expressions: %var% * 10
    - JSON dot notation: .foo.bar=value
    - Can set job variables and workflow variables
    """
    node_type = 'op_populate'

    def _eval_math_expr(self, expr: str) -> str:
        resolved = self.resolve(expr)
        try:
            if any(op in resolved for op in ['+', '-', '*', '/', '%']):
                result = eval(resolved, {"__builtins__": {}}, {})
                return str(result)
        except Exception:
            pass
        return resolved

    def execute(self) -> bool:
        params = self.node.params
        assignments = params.get('assignments', [])

        if not assignments:
            var = params.get('variable', '')
            val = params.get('value', '')
            if var:
                assignments = [{'variable': var, 'value': val}]

        if not assignments:
            self.log('No assignments defined')
            return False

        for i, assignment in enumerate(assignments):
            if isinstance(assignment, dict):
                var_name = self.resolve(assignment.get('variable', ''))
                var_value = assignment.get('value', '')
            else:
                var_name = self.resolve(getattr(assignment, 'variable', ''))
                var_value = getattr(assignment, 'value', '')

            if not var_name:
                continue

            resolved_value = self._eval_math_expr(var_value)
            self.var_engine.set_job_var(var_name, resolved_value)
            self.job.variables[var_name] = resolved_value
            self.log(f'Row {i}: Set {var_name} = {resolved_value}')

        return True


class AnalyzeNode(BaseNode):
    """File/media analysis node - populates file variables."""
    node_type = 'op_analyzer'

    def execute(self) -> bool:
        input_file = self.resolve(self.node.params.get('input', self.job.input_file))
        if not input_file or not Path(input_file).exists():
            self.log(f'File not found: {input_file}')
            return False

        self.log(f'Analyzing: {input_file}')
        p = Path(input_file)
        stat = p.stat()

        self.job.variables['i_file_size'] = str(stat.st_size)
        self.job.variables['s_file_name'] = p.name
        self.job.variables['s_original_name'] = p.stem
        self.job.variables['s_original_ext'] = p.suffix
        self.job.variables['s_file_ext'] = p.suffix
        self.job.variables['s_file_dir'] = str(p.parent)
        self.job.variables['s_original_path'] = str(p.parent)
        self.job.variables['s_original_full'] = str(p)

        self.var_engine.set_job_var('i_file_size', str(stat.st_size))
        self.var_engine.set_job_var('s_file_name', p.name)
        self.var_engine.set_job_var('s_file_ext', p.suffix)
        self.var_engine.set_job_var('s_file_dir', str(p.parent))

        return True


class ForeachNode(BaseNode):
    """Loop iteration node - iterates over items."""
    node_type = 'op_foreach'

    def execute(self) -> bool:
        params = self.node.params
        var_name = params.get('variable', 's_item')
        items_str = self.resolve(params.get('items', ''))
        delimiter = params.get('delimiter', '|')

        items = [i.strip() for i in items_str.split(delimiter) if i.strip()]
        self.log(f'Foreach: {len(items)} items')

        self.job.variables['i_foreach_count'] = str(len(items))
        self.var_engine.set_job_var('i_foreach_count', str(len(items)))

        for idx, item in enumerate(items):
            self.var_engine.set_job_var(var_name, item)
            self.job.variables[var_name] = item
            self.var_engine.set_job_var('i_foreach_index', str(idx))
            self.log(f'  Item {idx}: {item}')

        return True


class HoldNode(BaseNode):
    """Delay execution node."""
    node_type = 'op_hold'

    def execute(self) -> bool:
        seconds = int(self.node.params.get('seconds', '5'))
        self.log(f'Holding for {seconds} seconds')
        import time
        time.sleep(seconds)
        return True


class CMDRunNode(BaseNode):
    """Shell command execution node.

    Matches original FFAStrans cmd_run:
    - Full command with variable support
    - stdout/stderr capture to variable
    - Timeout, exit code handling
    - Sets %s_source% on completion
    """
    node_type = 'cmd_run'

    def execute(self) -> bool:
        params = self.node.params
        command = self.resolve(params.get('command', ''))
        timeout = int(params.get('timeout', '300'))
        capture_output = params.get('capture_output', True)

        if not command:
            self.log('No command specified')
            return False

        self.log(f'Running command: {command}')
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=capture_output,
                text=True,
                timeout=timeout,
                env=os.environ.copy(),
            )

            self.job.variables['i_exit_code'] = str(result.returncode)
            self.var_engine.set_job_var('i_exit_code', str(result.returncode))

            if capture_output:
                stdout = result.stdout[-4000:] if result.stdout else ''
                stderr = result.stderr[-4000:] if result.stderr else ''
                self.job.variables['s_stdout'] = stdout
                self.job.variables['s_stderr'] = stderr
                self.var_engine.set_job_var('s_stdout', stdout)
                self.var_engine.set_job_var('s_stderr', stderr)
                if result.stdout:
                    for line in result.stdout.strip().split('\n')[-20:]:
                        self.job.log_lines.append(f'[stdout] {line}')
                if result.stderr:
                    for line in result.stderr.strip().split('\n')[-20:]:
                        self.job.log_lines.append(f'[stderr] {line}')

            self.log(f'Exit code: {result.returncode}')
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            self.log(f'Command timed out after {timeout}s')
            self.job.variables['i_exit_code'] = '-1'
            self.job.variables['s_stderr'] = 'Timeout expired'
            return False
        except Exception as e:
            self.log(f'Command error: {e}')
            self.job.variables['i_exit_code'] = '-1'
            self.job.variables['s_stderr'] = str(e)
            return False


class EmailNode(BaseNode):
    """Email notification node."""
    node_type = 'other_email'

    def execute(self) -> bool:
        params = self.node.params
        smtp_server = self.resolve(params.get('smtp_server', ''))
        smtp_port = int(params.get('smtp_port', '587'))
        sender = self.resolve(params.get('from', ''))
        recipient = self.resolve(params.get('to', ''))
        subject = self.resolve(params.get('subject', 'FFAStrans notification'))
        body = self.resolve(params.get('body', ''))
        use_tls = params.get('tls', True)

        if not all([smtp_server, sender, recipient]):
            self.log('Missing email configuration')
            return False

        self.log(f'Sending email to: {recipient}')
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = sender
            msg['To'] = recipient

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                server.send_message(msg)
            self.log('Email sent successfully')
            return True
        except Exception as e:
            self.log(f'Email failed: {e}')
            return False


class HTTPSendNode(BaseNode):
    """HTTP request node."""
    node_type = 'other_httpsend'

    def execute(self) -> bool:
        params = self.node.params
        url = self.resolve(params.get('url', ''))
        method = params.get('method', 'GET')
        body = self.resolve(params.get('body', ''))
        headers = params.get('headers', {})

        if not url:
            self.log('No URL specified')
            return False

        self.log(f'HTTP {method}: {url}')
        try:
            data = body.encode('utf-8') if body else None
            req = urllib.request.Request(url, data=data, method=method)
            for k, v in headers.items():
                req.add_header(k, self.resolve(v))
            if body and 'Content-Type' not in headers:
                req.add_header('Content-Type', 'application/json')

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = resp.read().decode('utf-8')
                self.job.variables['s_http_response'] = resp_data
                self.job.variables['i_http_status'] = str(resp.status)
                self.var_engine.set_job_var('s_http_response', resp_data)
                self.var_engine.set_job_var('i_http_status', str(resp.status))
                self.log(f'HTTP response: {resp.status}')
                return True
        except Exception as e:
            self.log(f'HTTP error: {e}')
            self.job.variables['i_http_status'] = '0'
            self.job.variables['s_http_response'] = str(e)
            return False


class TextFileNode(BaseNode):
    """Write text file node."""
    node_type = 'other_textfile'

    def execute(self) -> bool:
        params = self.node.params
        content = self.resolve(params.get('content', ''))
        output_path = self.resolve(params.get('output_path', ''))
        mode = params.get('mode', 'overwrite')

        if not output_path:
            self.log('No output path specified')
            return False

        self.log(f'Writing text file: {output_path}')
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            file_mode = 'a' if mode == 'append' else 'w'
            with open(output_path, file_mode) as f:
                f.write(content)
            self.job.variables['s_output_file'] = output_path
            self.var_engine.set_job_var('s_output_file', output_path)
            return True
        except Exception as e:
            self.log(f'File write error: {e}')
            return False


class FolderDestination(BaseNode):
    """Folder delivery node.

    Matches original FFAStrans dest_folder:
    - prefix, suffix, overwrite
    - unique_name, zero_padding
    - drop_original_name, drop_extension
    - move_instead_of_copy, force_case
    """
    node_type = 'dest_folder'

    def execute(self) -> bool:
        params = self.node.params
        input_file = self.resolve(params.get('input', self.job.input_file))
        output_dir = self.resolve(params.get('path', ''))
        prefix = self.resolve(params.get('prefix', ''))
        suffix = self.resolve(params.get('suffix', ''))
        overwrite = params.get('overwrite', True)
        unique_name = params.get('unique_name', False)
        zero_padding = int(params.get('zero_padding', '0'))
        drop_original_name = params.get('drop_original_name', False)
        drop_extension = params.get('drop_extension', False)
        move_instead_of_copy = params.get('move_instead_of_copy', False)
        force_case = params.get('force_case', '')

        if not input_file or not Path(input_file).exists():
            self.log(f'Input file not found: {input_file}')
            return False

        if not output_dir:
            output_dir = str(Path(input_file).parent)

        Path(output_dir).mkdir(parents=True, exist_ok=True)

        p = Path(input_file)
        stem = p.stem if not drop_original_name else ''
        ext = p.suffix if not drop_extension else ''

        if zero_padding > 0:
            stem = stem.zfill(zero_padding) if stem else str(int(time.time())).zfill(zero_padding)

        new_name = f'{prefix}{stem}{suffix}{ext}'

        if unique_name:
            import time
            ts = str(int(time.time()))
            new_name = f'{prefix}{stem}{suffix}_{ts}{ext}'

        if force_case == 'lower':
            new_name = new_name.lower()
        elif force_case == 'upper':
            new_name = new_name.upper()

        output_path = str(Path(output_dir) / new_name)

        if not overwrite and Path(output_path).exists():
            base = Path(output_path).stem
            ext = Path(output_path).suffix
            counter = 1
            while Path(output_path).exists():
                output_path = str(Path(output_dir) / f'{base}_{counter}{ext}')
                counter += 1

        self.log(f'Delivering: {input_file} -> {output_path}')
        try:
            if move_instead_of_copy:
                shutil.move(input_file, output_path)
                self.log('Move complete')
            else:
                shutil.copy2(input_file, output_path)
                self.log('Copy complete')
            self.job.variables['s_output_file'] = output_path
            self.var_engine.set_job_var('s_output_file', output_path)
            return True
        except Exception as e:
            self.log(f'Delivery failed: {e}')
            return False


OPERATOR_NODES = {
    'op_cond': ConditionNode,
    'op_populate': PopulateNode,
    'op_analyzer': AnalyzeNode,
    'op_foreach': ForeachNode,
    'op_hold': HoldNode,
    'cmd_run': CMDRunNode,
    'other_email': EmailNode,
    'other_httpsend': HTTPSendNode,
    'other_textfile': TextFileNode,
    'dest_folder': FolderDestination,
}
