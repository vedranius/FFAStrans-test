"""Global configuration for FFAStrans Linux Mimo."""
import os
import platform
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
WORKFLOW_DIR = DATA_DIR / "workflows"
JOB_DIR = DATA_DIR / "jobs"
LOG_DIR = DATA_DIR / "logs"
PRESETS_DIR = BASE_DIR / "ffastrans" / "presets"

INPUT_DIR = Path(os.getenv("FFASTRANS_INPUT_DIR", str(BASE_DIR / "drop_folders" / "input")))
OUTPUT_DIR = Path(os.getenv("FFASTRANS_OUTPUT_DIR", str(BASE_DIR / "drop_folders" / "output")))

HOSTNAME = os.getenv("FFASTRANS_HOSTNAME", platform.node())
API_PORT = int(os.getenv("FFASTRANS_API_PORT", "8080"))
API_HOST = os.getenv("FFASTRANS_API_HOST", "0.0.0.0")
SECRET_KEY = os.getenv("FFASTRANS_SECRET_KEY", "change-me-in-production")

FFMPEG_PATH = os.getenv("FFASTRANS_FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFASTRANS_FFPROBE_PATH", "ffprobe")
MEDIAINFO_PATH = os.getenv("FFASTRANS_MEDIAINFO_PATH", "mediainfo")
EXIFTOOL_PATH = os.getenv("FFASTRANS_EXIFTOOL_PATH", "exiftool")

MAX_CONCURRENT_JOBS = int(os.getenv("FFASTRANS_MAX_CONCURRENT_JOBS", "4"))
NODE_REGISTRATION_INTERVAL = int(os.getenv("FFASTRANS_NODE_REGISTRATION_INTERVAL", "5"))
NODE_TIMEOUT = int(os.getenv("FFASTRANS_NODE_TIMEOUT", "30"))

NODE_ROLE = os.getenv("FFASTRANS_NODE_ROLE", "master")
REMOTE_NODE_URL = os.getenv("FFASTRANS_REMOTE_NODE_URL", "")

for d in [DATA_DIR, WORKFLOW_DIR, JOB_DIR, LOG_DIR, INPUT_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def load_config():
    cfg_path = DATA_DIR / "config.json"
    if cfg_path.exists():
        with open(cfg_path, "r") as f:
            return json.load(f)
    return {}


def save_config(cfg: dict):
    cfg_path = DATA_DIR / "config.json"
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
