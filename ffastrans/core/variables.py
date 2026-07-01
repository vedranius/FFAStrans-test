"""Variable interpolation engine - resolves %%variable%% placeholders."""
import os
import re
import time
from datetime import datetime
from pathlib import Path


class VariableEngine:
    VAR_PATTERN = re.compile(r'%%(\w+)%%')
    FUNC_PATTERN = re.compile(r'%%(\w+)\(([^)]*)\)%%')

    SYSTEM_VARS = {
        "s_date": lambda: datetime.now().strftime("%Y%m%d"),
        "s_time": lambda: datetime.now().strftime("%H%M%S"),
        "s_datetime": lambda: datetime.now().strftime("%Y%m%d_%H%M%S"),
        "s_year": lambda: datetime.now().strftime("%Y"),
        "s_month": lambda: datetime.now().strftime("%m"),
        "s_day": lambda: datetime.now().strftime("%d"),
        "s_hour": lambda: datetime.now().strftime("%H"),
        "s_minute": lambda: datetime.now().strftime("%M"),
        "s_second": lambda: datetime.now().strftime("%S"),
        "s_hostname": lambda: os.uname().nodename,
        "s_user": lambda: os.getenv("USER", "root"),
        "i_pid": lambda: str(os.getpid()),
    }

    def __init__(self, user_vars: dict = None, job_vars: dict = None):
        self.user_vars = user_vars or {}
        self.job_vars = job_vars or {}

    def resolve(self, text: str) -> str:
        if not isinstance(text, str):
            return str(text)

        def replace_func(m):
            func_name = m.group(1)
            args_str = m.group(2)
            return self._eval_function(func_name, args_str)

        text = self.FUNC_PATTERN.sub(replace_func, text)

        def replace_var(m):
            var_name = m.group(1)
            return self._get_var(var_name)

        return self.VAR_PATTERN.sub(replace_var, text)

    def _get_var(self, name: str) -> str:
        if name in self.job_vars:
            return str(self.job_vars[name])
        if name in self.user_vars:
            val = self.user_vars[name]
            if callable(val):
                return str(val())
            return str(val)
        if name in self.SYSTEM_VARS:
            return str(self.SYSTEM_VARS[name]())
        return f"%%{name}%%"

    def _eval_function(self, func_name: str, args_str: str) -> str:
        args = [a.strip().strip('"').strip("'") for a in args_str.split(",") if a.strip()]
        if func_name == "str_upper":
            return self.resolve(args[0]).upper() if args else ""
        elif func_name == "str_lower":
            return self.resolve(args[0]).lower() if args else ""
        elif func_name == "str_trim":
            return self.resolve(args[0]).strip() if args else ""
        elif func_name == "str_replace":
            if len(args) >= 3:
                return self.resolve(args[0]).replace(self.resolve(args[1]), self.resolve(args[2]))
            return self.resolve(args[0]) if args else ""
        elif func_name == "str_substr":
            if len(args) >= 3:
                s = self.resolve(args[0])
                start = int(self.resolve(args[1]))
                length = int(self.resolve(args[2]))
                return s[start:start + length]
            return self.resolve(args[0]) if args else ""
        elif func_name == "str_len":
            return str(len(self.resolve(args[0]))) if args else "0"
        elif func_name == "str_pad":
            if len(args) >= 3:
                s = self.resolve(args[0])
                length = int(self.resolve(args[1]))
                char = self.resolve(args[2])
                return s.ljust(length, char)
            return self.resolve(args[0]) if args else ""
        elif func_name == "i_add":
            vals = [int(self.resolve(a)) for a in args]
            return str(sum(vals)) if vals else "0"
        elif func_name == "i_sub":
            if len(args) >= 2:
                return str(int(self.resolve(args[0])) - int(self.resolve(args[1])))
            return "0"
        elif func_name == "i_mul":
            vals = [int(self.resolve(a)) for a in args]
            result = 1
            for v in vals:
                result *= v
            return str(result)
        elif func_name == "i_div":
            if len(args) >= 2:
                d = int(self.resolve(args[1]))
                return str(int(self.resolve(args[0])) // d) if d else "0"
            return "0"
        elif func_name == "file_ext":
            p = Path(self.resolve(args[0])) if args else Path("")
            return p.suffix
        elif func_name == "file_name":
            p = Path(self.resolve(args[0])) if args else Path("")
            return p.stem
        elif func_name == "file_dir":
            p = Path(self.resolve(args[0])) if args else Path("")
            return str(p.parent)
        elif func_name == "file_size":
            p = Path(self.resolve(args[0])) if args else Path("")
            return str(p.stat().st_size) if p.exists() else "0"
        return f"%%{func_name}({args_str})%%"
