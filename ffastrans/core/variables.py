"""Variable interpolation engine - resolves %variable% placeholders.

Matches original FFAStrans variable system:
- Variables: %prefix_name% (single % delimiter)
- Functions: $function(arg1, arg2, ...) (dollar sign prefix)
- Prefixes: s_ (string), i_ (integer), f_ (float), o_ (JSON), S_ (static)
"""
import os
import platform
import re
import time
import hashlib
import math
import random
import uuid
import base64
import urllib.parse
import json
import glob as globmod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


class VariableEngine:
    """Resolves %variable% and $function() expressions."""

    VAR_PATTERN = re.compile(r'%([a-zA-Z_][a-zA-Z0-9_]*)%')
    FUNC_PATTERN = re.compile(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\(([^)]*)\)')
    NESTED_FUNC = re.compile(r'\$([a-zA-Z_][a-zA-Z0-9_]*)\(([^$()]*(?:\$(?:[a-zA-Z_]\w*\([^)]*\))[^$()]*)*)\)')

    def __init__(self, user_vars: dict = None, job_vars: dict = None,
                 workflow_vars: dict = None, system_vars: dict = None):
        self.user_vars = user_vars or {}
        self.job_vars = job_vars or {}
        self.workflow_vars = workflow_vars or {}
        self._static_vars: dict = {}
        self._evaluated_once: set = set()

    def set_static_var(self, name: str, value: str):
        self._static_vars[name] = value

    def get_static_var(self, name: str) -> Optional[str]:
        return self._static_vars.get(name)

    def set_job_var(self, name: str, value: str):
        self.job_vars[name] = str(value)

    def get_var(self, name: str) -> str:
        if name in self._static_vars:
            return self._static_vars[name]
        if name in self.job_vars:
            val = self.job_vars[name]
            if callable(val):
                return str(val())
            return str(val)
        if name in self.workflow_vars:
            val = self.workflow_vars[name]
            if callable(val):
                return str(val())
            return str(val)
        if name in self.user_vars:
            val = self.user_vars[name]
            if callable(val):
                return str(val())
            return str(val)
        if name in _SYSTEM_VARS:
            val = _SYSTEM_VARS[name]
            if callable(val):
                return str(val(self))
            return str(val)
        return f'%{name}%'

    def resolve(self, text: str, max_depth: int = 10) -> str:
        if not isinstance(text, str):
            return str(text)
        for _ in range(max_depth):
            new_text = self._resolve_once(text)
            if new_text == text:
                break
            text = new_text
        return text

    def _resolve_once(self, text: str) -> str:
        text = self._resolve_functions(text)
        text = self._resolve_variables(text)
        return text

    def _resolve_variables(self, text: str) -> str:
        def replace_var(m):
            var_name = m.group(1)
            return self.get_var(var_name)
        return self.VAR_PATTERN.sub(replace_var, text)

    def _resolve_functions(self, text: str) -> str:
        max_iter = 20
        for _ in range(max_iter):
            new_text = self.FUNC_PATTERN.sub(lambda m: self._eval_function(m.group(1), m.group(2)), text)
            if new_text == text:
                break
            text = new_text
        return text

    def _parse_args(self, args_str: str) -> list[str]:
        args = []
        current = ""
        depth = 0
        in_string = False
        string_char = None
        for ch in args_str:
            if in_string:
                current += ch
                if ch == string_char:
                    in_string = False
                continue
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                current += ch
            elif ch == '(':
                depth += 1
                current += ch
            elif ch == ')':
                depth -= 1
                current += ch
            elif ch == ',' and depth == 0:
                args.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            args.append(current.strip())
        return args

    def _eval_function(self, func_name: str, args_str: str) -> str:
        raw_args = self._parse_args(args_str)
        args = [self.resolve(a.strip().strip('"').strip("'")) for a in raw_args if a.strip()]

        func_map = {
            'string': self._func_string,
            'replace': self._func_replace,
            'regreplace': self._func_regreplace,
            'left': self._func_left,
            'middle': self._func_middle,
            'right': self._func_right,
            'upper': self._func_upper,
            'lower': self._func_lower,
            'stripws': self._func_stripws,
            'stripcrlf': self._func_stripcrlf,
            'length': self._func_length,
            'isdigit': self._func_isdigit,
            'isalpha': self._func_isalpha,
            'reverse': self._func_reverse,
            'triml': self._func_triml,
            'trimr': self._func_trimr,
            'round': self._func_round,
            'roundd': self._func_roundd,
            'roundu': self._func_roundu,
            'leads': self._func_leads,
            'trails': self._func_trails,
            'between': self._func_between,
            'proper': self._func_proper,
            'alrep': self._func_alrep,
            'exists': self._func_exists,
            'read': self._func_read,
            'inttotc': self._func_inttotc,
            'tctosec': self._func_tctosec,
            'regext': self._func_regext,
            'abs': self._func_abs,
            'log': self._func_log,
            'random': self._func_random,
            'hex': self._func_hex,
            'dec': self._func_dec,
            'guid': self._func_guid,
            'base64': self._func_base64,
            'base64dec': self._func_base64dec,
            'urlencode': self._func_urlencode,
            'jsonencode': self._func_jsonencode,
            'readarray': self._func_readarray,
            'week': self._func_week,
            'weekday': self._func_weekday,
            'lookup': self._func_lookup,
            'lookuprep': self._func_lookuprep,
            'sort': self._func_sort,
            'count': self._func_count,
            'foreach': self._func_foreach,
            'stringf': self._func_stringf,
            'fsize': self._func_fsize,
            'fext': self._func_fext,
            'fname': self._func_fname,
            'fpath': self._func_fpath,
            'fdrive': self._func_fdrive,
            'asplit': self._func_asplit,
            'ffconcat': self._func_ffconcat,
            'owner': self._func_owner,
            'waccess': self._func_waccess,
            'dateweek': self._func_dateweek,
            'timecalc': self._func_timecalc,
            'shortcut': self._func_shortcut,
            'jsonget': self._func_jsonget,
            'jsonput': self._func_jsonput,
            'xxhash': self._func_xxhash,
            'xxhash64': self._func_xxhash64,
        }

        if func_name in func_map:
            try:
                return str(func_map[func_name](args))
            except Exception:
                return f'${func_name}({args_str})'
        return f'${func_name}({args_str})'

    def _func_string(self, args: list) -> str:
        return args[0] if args else ''

    def _func_replace(self, args: list) -> str:
        if len(args) < 3:
            return args[0] if args else ''
        s, find, repl = args[0], args[1], args[2]
        mode = args[3] if len(args) > 3 else '0'
        if mode == '1':
            return re.sub(re.escape(find), repl, s, flags=re.IGNORECASE)
        return s.replace(find, repl)

    def _func_regreplace(self, args: list) -> str:
        if len(args) < 3:
            return args[0] if args else ''
        return re.sub(args[1], args[2], args[0])

    def _func_left(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        return args[0][:int(args[1])]

    def _func_middle(self, args: list) -> str:
        if len(args) < 3:
            return args[0] if args else ''
        start = int(args[1])
        length = int(args[2])
        return args[0][start:start + length]

    def _func_right(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        n = int(args[1])
        return args[0][-n:] if n > 0 else ''

    def _func_upper(self, args: list) -> str:
        return args[0].upper() if args else ''

    def _func_lower(self, args: list) -> str:
        return args[0].lower() if args else ''

    def _func_stripws(self, args: list) -> str:
        return args[0].strip() if args else ''

    def _func_stripcrlf(self, args: list) -> str:
        return args[0].strip().strip('\r\n') if args else ''

    def _func_length(self, args: list) -> str:
        return str(len(args[0])) if args else '0'

    def _func_isdigit(self, args: list) -> str:
        return '1' if args and args[0].isdigit() else '0'

    def _func_isalpha(self, args: list) -> str:
        return '1' if args and args[0].isalpha() else '0'

    def _func_reverse(self, args: list) -> str:
        return args[0][::-1] if args else ''

    def _func_triml(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        return args[0][int(args[1]):]

    def _func_trimr(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        return args[0][:-int(args[1])] if int(args[1]) > 0 else args[0]

    def _func_round(self, args: list) -> str:
        if not args:
            return '0'
        val = float(args[0])
        dec = int(args[1]) if len(args) > 1 else 0
        return str(round(val, dec))

    def _func_roundd(self, args: list) -> str:
        return str(math.floor(float(args[0]))) if args else '0'

    def _func_roundu(self, args: list) -> str:
        return str(math.ceil(float(args[0]))) if args else '0'

    def _func_leads(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        s, n = args[0], int(args[1])
        fill = args[2] if len(args) > 2 else ' '
        return s.zfill(n) if fill == '0' else s.rjust(n, fill)

    def _func_trails(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        s, n = args[0], int(args[1])
        fill = args[2] if len(args) > 2 else ' '
        return s.ljust(n, fill)

    def _func_between(self, args: list) -> str:
        if len(args) < 3:
            return ''
        s, start, end = args[0], args[1], args[2]
        instance = int(args[3]) if len(args) > 3 else 0
        idx_s = s.find(start)
        if idx_s == -1:
            return ''
        idx_s += len(start)
        idx_e = s.find(end, idx_s)
        if idx_e == -1:
            return ''
        return s[idx_s:idx_e]

    def _func_proper(self, args: list) -> str:
        return args[0].title() if args else ''

    def _func_alrep(self, args: list) -> str:
        if not args:
            return ''
        s = args[0]
        repl = args[1] if len(args) > 1 else '*'
        except_chars = args[2] if len(args) > 2 else ''
        result = []
        for ch in s:
            if ch.isalpha() and ch not in except_chars:
                result.append(repl)
            else:
                result.append(ch)
        return ''.join(result)

    def _func_exists(self, args: list) -> str:
        if not args:
            return '0'
        path = args[0]
        mode = args[1] if len(args) > 1 else 'e'
        recursive = args[2] if len(args) > 2 else '0'
        p = Path(path)
        if mode == 'd':
            return '1' if p.is_dir() else '0'
        elif mode == 'f':
            return '1' if p.is_file() else '0'
        elif mode == 'r':
            return '1' if os.access(path, os.R_OK) else '0'
        elif mode == 'w':
            return '1' if os.access(path, os.W_OK) else '0'
        return '1' if p.exists() else '0'

    def _func_read(self, args: list) -> str:
        if not args:
            return ''
        try:
            return Path(args[0]).read_text()
        except Exception:
            return ''

    def _func_inttotc(self, args: list) -> str:
        if len(args) < 2:
            return '00:00:00:00'
        frames = int(args[0])
        fps_parts = args[1].split('/')
        if len(fps_parts) == 2:
            fps = float(fps_parts[0]) / float(fps_parts[1])
        else:
            fps = float(args[1])
        total_seconds = frames / fps
        h = int(total_seconds // 3600)
        m = int((total_seconds % 3600) // 60)
        s = int(total_seconds % 60)
        f = int((total_seconds % 1) * fps)
        return f'{h:02d}:{m:02d}:{s:02d}:{f:02d}'

    def _func_tctosec(self, args: list) -> str:
        if len(args) < 2:
            return '0'
        parts = args[0].split(':')
        fps_parts = args[1].split('/')
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(args[1])
        if len(parts) == 4:
            h, m, s, f = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            return str(h * 3600 + m * 60 + s + f / fps)
        elif len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return str(h * 3600 + m * 60 + s)
        return '0'

    def _func_regext(self, args: list) -> str:
        if len(args) < 2:
            return ''
        match = re.search(args[1], args[0])
        return match.group(1) if match and match.lastindex else (match.group(0) if match else '')

    def _func_abs(self, args: list) -> str:
        return str(abs(float(args[0]))) if args else '0'

    def _func_log(self, args: list) -> str:
        return str(math.log(float(args[0]))) if args else '0'

    def _func_random(self, args: list) -> str:
        if len(args) < 2:
            return str(random.randint(0, 100))
        return str(random.randint(int(args[0]), int(args[1])))

    def _func_hex(self, args: list) -> str:
        return hex(int(args[0]))[2:] if args else '0'

    def _func_dec(self, args: list) -> str:
        return str(int(args[0], 16)) if args else '0'

    def _func_guid(self, args: list) -> str:
        return str(uuid.uuid4())

    def _func_base64(self, args: list) -> str:
        return base64.b64encode(args[0].encode()).decode() if args else ''

    def _func_base64dec(self, args: list) -> str:
        return base64.b64decode(args[0]).decode() if args else ''

    def _func_urlencode(self, args: list) -> str:
        return urllib.parse.quote(args[0]) if args else ''

    def _func_jsonencode(self, args: list) -> str:
        return json.dumps(args[0]) if args else ''

    def _func_readarray(self, args: list) -> str:
        if len(args) < 2:
            return ''
        arr = args[0].split('|')
        idx = int(args[1])
        zero_based = args[2] == '0' if len(args) > 2 else True
        if not zero_based:
            idx -= 1
        return arr[idx] if 0 <= idx < len(arr) else ''

    def _func_week(self, args: list) -> str:
        now = datetime.now()
        return str(now.isocalendar()[1])

    def _func_weekday(self, args: list) -> str:
        return str(datetime.now().isoweekday())

    def _func_lookup(self, args: list) -> str:
        if len(args) < 3:
            return ''
        search_val = args[0]
        table = args[1].split('|')
        for entry in table:
            parts = entry.split('=')
            if len(parts) == 2 and parts[0].strip() == search_val:
                return parts[1].strip()
        return ''

    def _func_lookuprep(self, args: list) -> str:
        if len(args) < 3:
            return args[0] if args else ''
        search_val = args[0]
        table = args[1].split('|')
        for entry in table:
            parts = entry.split('=')
            if len(parts) == 2 and parts[0].strip() == search_val:
                return parts[1].strip()
        return search_val

    def _func_sort(self, args: list) -> str:
        if not args:
            return ''
        sep = args[1] if len(args) > 1 else '|'
        items = args[0].split(sep)
        return sep.join(sorted(items))

    def _func_count(self, args: list) -> str:
        if len(args) < 2:
            return '0'
        return str(args[0].count(args[1]))

    def _func_foreach(self, args: list) -> str:
        if len(args) < 2:
            return ''
        items = args[0].split('|')
        op = args[1] if len(args) > 1 else 'count'
        if op == 'count':
            return str(len(items))
        elif op == 'first':
            return items[0] if items else ''
        elif op == 'last':
            return items[-1] if items else ''
        elif op == 'join':
            sep = args[2] if len(args) > 2 else ','
            return sep.join(items)
        return args[0]

    def _func_stringf(self, args: list) -> str:
        if len(args) < 2:
            return args[0] if args else ''
        fmt = args[0]
        try:
            return fmt % tuple(args[1:])
        except Exception:
            return fmt

    def _func_fsize(self, args: list) -> str:
        if not args:
            return '0'
        try:
            return str(Path(args[0]).stat().st_size)
        except Exception:
            return '0'

    def _func_fext(self, args: list) -> str:
        return Path(args[0]).suffix if args else ''

    def _func_fname(self, args: list) -> str:
        return Path(args[0]).stem if args else ''

    def _func_fpath(self, args: list) -> str:
        return str(Path(args[0]).parent) if args else ''

    def _func_fdrive(self, args: list) -> str:
        return Path(args[0]).drive if args else ''

    def _func_asplit(self, args: list) -> str:
        if not args:
            return ''
        sep = args[1] if len(args) > 1 else '|'
        return args[0].replace(sep, ',')

    def _func_ffconcat(self, args: list) -> str:
        if not args:
            return ''
        items = args[0].split('|')
        lines = ["file '" + item + "'" for item in items]
        return '\n'.join(lines)

    def _func_owner(self, args: list) -> str:
        if not args:
            return ''
        try:
            import pwd
            stat = os.stat(args[0])
            return pwd.getpwuid(stat.st_uid).pw_name
        except Exception:
            return ''

    def _func_waccess(self, args: list) -> str:
        return '1' if args and os.access(args[0], os.W_OK) else '0'

    def _func_dateweek(self, args: list) -> str:
        if len(args) < 3:
            return ''
        y, w, d = int(args[0]), int(args[1]), int(args[2])
        start = int(args[3]) if len(args) > 3 else 1
        jan4 = datetime(y, 1, 4)
        start_of_week = jan4 - timedelta(days=jan4.weekday())
        target = start_of_week + timedelta(weeks=w - 1, days=d - start)
        return target.strftime('%Y%m%d')

    def _func_timecalc(self, args: list) -> str:
        if len(args) < 3:
            return ''
        unit = args[0]
        amount = int(args[1])
        dt_str = args[2]
        try:
            dt = datetime.strptime(dt_str, '%Y%m%d_%H%M%S')
        except Exception:
            dt = datetime.now()
        if unit == 'y':
            dt += timedelta(days=amount * 365)
        elif unit == 'mo':
            dt += timedelta(days=amount * 30)
        elif unit == 'w':
            dt += timedelta(weeks=amount)
        elif unit == 'd':
            dt += timedelta(days=amount)
        elif unit == 'h':
            dt += timedelta(hours=amount)
        elif unit == 'mi':
            dt += timedelta(minutes=amount)
        elif unit == 's':
            dt += timedelta(seconds=amount)
        return dt.strftime('%Y%m%d_%H%M%S')

    def _func_shortcut(self, args: list) -> str:
        if not args:
            return ''
        return str(Path(args[0]).resolve())

    def _func_jsonget(self, args: list) -> str:
        if len(args) < 2:
            return ''
        try:
            data = json.loads(args[0]) if isinstance(args[0], str) else args[0]
            path_parts = args[1].split('.')
            for part in path_parts:
                if isinstance(data, dict):
                    data = data.get(part, '')
                else:
                    return ''
            return json.dumps(data) if isinstance(data, (dict, list)) else str(data)
        except Exception:
            return ''

    def _func_jsonput(self, args: list) -> str:
        if len(args) < 3:
            return args[0] if args else ''
        try:
            data = json.loads(args[0]) if isinstance(args[0], str) else {}
            path_parts = args[1].split('.')
            current = data
            for part in path_parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            current[path_parts[-1]] = args[2]
            return json.dumps(data)
        except Exception:
            return args[0] if args else ''

    def _xxhash(self, data: bytes) -> str:
        try:
            import xxhash
            return xxhash.xxh64(data).hexdigest()
        except ImportError:
            h = hashlib.sha256(data).hexdigest()
            return h[:16]

    def _func_xxhash(self, args: list) -> str:
        if not args:
            return ''
        try:
            data = Path(args[0]).read_bytes()
            return self._xxhash(data)[:8]
        except Exception:
            return ''

    def _func_xxhash64(self, args: list) -> str:
        if not args:
            return ''
        try:
            data = Path(args[0]).read_bytes()
            return self._xxhash(data)[:16]
        except Exception:
            return ''


def _get_s_hostname(eng: VariableEngine) -> str:
    return platform.node()

def _get_s_date(eng: VariableEngine) -> str:
    return datetime.now().strftime('%Y%m%d')

def _get_s_time(eng: VariableEngine) -> str:
    return datetime.now().strftime('%H%M%S')

def _get_s_datetime(eng: VariableEngine) -> str:
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def _get_s_year(eng: VariableEngine) -> str:
    return datetime.now().strftime('%Y')

def _get_s_month(eng: VariableEngine) -> str:
    return datetime.now().strftime('%m')

def _get_s_day(eng: VariableEngine) -> str:
    return datetime.now().strftime('%d')

def _get_s_hour(eng: VariableEngine) -> str:
    return datetime.now().strftime('%H')

def _get_s_minute(eng: VariableEngine) -> str:
    return datetime.now().strftime('%M')

def _get_s_second(eng: VariableEngine) -> str:
    return datetime.now().strftime('%S')

def _get_s_week(eng: VariableEngine) -> str:
    return str(datetime.now().isocalendar()[1])

def _get_s_weekday(eng: VariableEngine) -> str:
    return str(datetime.now().isoweekday())

def _get_s_user(eng: VariableEngine) -> str:
    return os.getenv('USER', 'root')

def _get_i_pid(eng: VariableEngine) -> str:
    return str(os.getpid())

_SYSTEM_VARS = {
    's_hostname': _get_s_hostname,
    's_date': _get_s_date,
    's_time': _get_s_time,
    's_datetime': _get_s_datetime,
    's_year': _get_s_year,
    's_month': _get_s_month,
    's_day': _get_s_day,
    's_hour': _get_s_hour,
    's_minute': _get_s_minute,
    's_second': _get_s_second,
    's_week': _get_s_week,
    's_weekday': _get_s_weekday,
    's_user': _get_s_user,
    'i_pid': _get_i_pid,
}
