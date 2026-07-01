# FFAStrans Linux Mimo

**Free Workflow and Transcoding System for Linux**

Complete rewrite of [FFAStrans](https://github.com/vedranius/FFAStrans-test) for Linux - containerized with Docker and Kubernetes support, with a modern browser-based GUI.

## Features

- **Web-based GUI** - No Windows app needed, access from any browser
- **Workflow Editor** - Visual node-based workflow designer with drag & drop
- **Docker Support** - Ready-to-use containers for master and worker nodes
- **Kubernetes Support** - Production-ready K8s manifests with auto-scaling
- **Multi-node Processing** - Distributed transcoding across worker nodes
- **REST API** - Full API compatible with the original FFAStrans REST API
- **Drop Folder Monitoring** - Auto-detect new files in monitored directories
- **FFmpeg Integration** - All encoding/decoding via FFmpeg (no AviSynth dependency)
- **Multiple Formats** - H.264, H.265/HEVC, ProRes, DNxHR, AV1, MPEG, and more
- **Variable System** - Dynamic variables with string manipulation functions
- **Job Queue** - Priority-based job scheduling with pause/resume/abort
- **History & Logging** - Full job history and processing logs
- **Host Management** - Distributed node farm management

## Quick Start

### Docker Compose (Recommended)

```bash
git clone https://github.com/vedranius/FFAStrans-refactor_linux_mimo.git
cd FFAStrans-refactor_linux_mimo
docker-compose up -d
```

Open http://localhost:8080 in your browser.

### Direct Installation

```bash
# Requires Python 3.10+
sudo apt install ffmpeg mediainfo  # Ubuntu/Debian
# or
sudo dnf install ffmpeg mediainfo  # Fedora

pip install -r requirements.txt
python -m ffastrans.main
```

### Kubernetes

```bash
kubectl apply -f k8s/
```

## Architecture

```
ffastrans/
  api/          - FastAPI REST API (routes.py)
  core/         - Core engine (config, models, storage, engine, variables)
  nodes/        - Node processors (monitors, encoders, decoders, filters, operators)
  gui/          - Browser-based web interface (HTML/CSS/JS)
  workers/      - Worker node agent
  presets/      - Built-in encoder presets
```

## Node Types

### Monitors
| Node | Description |
|------|-------------|
| `mon_folder` | Watch folder for new files |
| `mon_sequence` | Image sequence detection |

### Decoders
| Node | Description |
|------|-------------|
| `dec_avmedia` | Probe and analyze media files |
| `dec_stills` | Convert still images to video |

### Encoders
| Node | Description |
|------|-------------|
| `enc_av_mp4` | H.264/MP4 encoding |
| `enc_av_265` | H.265/HEVC encoding |
| `enc_av_prores` | Apple ProRes encoding |
| `enc_av_dnxhr` | Avid DNxHR encoding |
| `enc_av_customff` | Custom FFmpeg arguments |
| `enc_a_audio` | Audio-only encoding |

### Filters
| Node | Description |
|------|-------------|
| `avs_v_resize` | Video resize/scale |
| `avs_v_crop` | Video crop |
| `avs_v_color` | Color correction |
| `avs_v_watermark` | Image watermark overlay |
| `avs_v_tc` | Timecode burn-in |
| `avs_v_deinterlace` | Deinterlacing |
| `avs_v_pad` | Add padding/borders |
| `avs_v_flip` | Horizontal/vertical flip |
| `avs_v_fpsconv` | Frame rate conversion |

### Operators
| Node | Description |
|------|-------------|
| `op_cond` | Conditional branching |
| `op_populate` | Variable template expansion |
| `op_analyzer` | File analysis |
| `op_foreach` | Loop over items |
| `op_hold` | Delay execution |

### Utilities
| Node | Description |
|------|-------------|
| `cmd_run` | Execute shell commands |
| `other_email` | Send email notifications |
| `other_httpsend` | HTTP API calls |
| `other_textfile` | Write text files |
| `dest_folder` | Copy to destination folder |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FFASTRANS_API_PORT` | 8080 | API port |
| `FFASTRANS_API_HOST` | 0.0.0.0 | API bind address |
| `FFASTRANS_NODE_ROLE` | master | Node role (master/node) |
| `FFASTRANS_REMOTE_NODE_URL` | - | Master URL for worker nodes |
| `FFASTRANS_MAX_CONCURRENT_JOBS` | 4 | Max simultaneous jobs |
| `FFASTRANS_INPUT_DIR` | drop_folders/input | Default input directory |
| `FFASTRANS_OUTPUT_DIR` | drop_folders/output | Default output directory |
| `FFASTRANS_FFMPEG_PATH` | ffmpeg | Path to FFmpeg binary |

## REST API

The API is fully compatible with the original FFAStrans REST API:

```
GET    /api/workflows              - List workflows
GET    /api/workflows/status       - Get workflow states
POST   /api/workflows              - Create/import workflow
PUT    /api/workflows/{id}         - Update workflow
PUT    /api/workflows/{id}/state   - Start/stop workflow
DELETE /api/workflows/{id}         - Delete workflow

GET    /api/jobs                   - List all jobs
GET    /api/jobs/active            - List active jobs
GET    /api/jobs/{id}              - Get job status
POST   /api/jobs                   - Submit new job
PUT    /api/jobs/{id}              - Pause/resume/abort job
DELETE /api/jobs/{id}              - Abort job

GET    /api/joblog/{id}            - Get job log
GET    /api/jobvars/{id}           - Get job variables
GET    /api/history                - Get history log

GET    /api/user_variables         - List user variables
POST   /api/user_variables         - Create user variable
GET    /api/presets                - List presets
GET    /api/nodes/available        - List available node types
GET    /api/hosts                  - List registered hosts
```

## Docker Compose Services

- `ffastrans-master` - Main server with web GUI and API
- `ffastrans-node-1` - Worker node 1
- `ffastrans-node-2` - Worker node 2

All services share the same volume for drop folders.

## License

MIT License - Same as the original FFAStrans.
