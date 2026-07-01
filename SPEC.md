# FFAStrans Linux Mimo - Technical Specification
## Based on R&D of original FFAStrans (vedranius/FFAStrans-test)

---

## 1. Architecture Overview

Original FFAStrans is a Windows-only AutoIt application with:
- GUI manager (FFAStrans.exe) - workflow editor
- REST service (rest_service.exe) - API + web monitor
- Queuer (FFAStrans_Queuer.exe) - job scheduling
- Processor engine (processors.a3x) - node execution
- Status monitor (status_monitor.a3x) - live monitoring
- AviSynth+ for video filtering pipeline
- FFmpeg for encoding/decoding

### Linux Rewrite Architecture:
```
ffastrans/
  server/          - FastAPI server (REST API + Web GUI)
  engine/          - Workflow execution engine
  nodes/           - Node processor implementations
  scheduler/       - Job queue with priority classes
  monitor/         - File monitor (folder watching)
  variables/       - Variable system with functions
  storage/         - JSON/SQLite persistence
  worker/          - Worker node agent (connects to master)
  gui/             - Browser-based web interface
```

## 2. Variable System (CRITICAL - must match original exactly)

### 2.1 Variable Notation
- Variables: `%prefix_variable_name%` (single % delimiter)
- Functions: `$function(arg1, arg2, ...)` (dollar sign prefix)
- Prefixes: `s_` (string), `i_` (integer), `f_` (float), `o_` (JSON), `S_` (static)
- Special: `%s_source%` (current input), `%s_error%`, `%s_success%`

### 2.2 Built-in Variables
**File variables** (from input file):
- `%s_original_full%`, `%s_original_path%`, `%s_original_name%`, `%s_original_ext%`
- `%s_original_path~N%` (N-steps backwards in path)

**Media variables** (from ffprobe/mediainfo):
- `%i_width%`, `%i_height%`, `%f_fps%`, `%s_v_codec%`, `%s_a_codec%`
- `%i_v_bitrate%`, `%i_a_bitrate%`, `%i_frames%`, `%f_duration%`
- `%o_media%` (full JSON probe data)

**Time variables**:
- `%s_date%`, `%s_time%`, `%s_datetime%`, `%i_year%`, `%i_month%`, `%i_day%`
- `%i_hour%`, `%i_minute%`, `%i_second%`, `%i_week%`, `%i_weekday%`

**System variables**:
- `%s_hostname%`, `%s_wf_name%`, `%s_wf_id%`, `%s_node_name%`, `%s_node_id%`
- `%s_job_id%`, `%s_cache_record%`

### 2.3 Functions (must implement ALL)
```
$string(str)           - String operations
$replace(str, find, replace [, type])  - Replace string
$regreplace(str, pattern, replace)     - Regex replace
$left(str, n)          - Left substring
$middle(str, start, n) - Middle substring
$right(str, n)         - Right substring
$upper(str)            - Uppercase
$lower(str)            - Lowercase
$stripws(str)          - Strip whitespace
$stripcrlf(str)        - Strip CR/LF
$length(str)           - String length
$isdigit(str)          - Is digits only
$isalpha(str)          - Is alpha only
$reverse(str)          - Reverse string
$triml(str, n)         - Trim left n chars
$trimr(str, n)         - Trim right n chars
$round(num [, dec])    - Round number
$roundd(num)           - Round down
$roundu(num)           - Round up
$leads(str, n [, fill])  - Leading chars
$trails(str, n [, fill]) - Trailing chars
$between(str, from, to [, instance]) - Extract between
$proper(str)           - Proper case
$alrep(str [, repl] [, except]) - Alpha replace
$exists(path [, mode] [, recursive]) - File exists
$read(path)            - Read file
$inttotc(frames, fps)  - Int to timecode
$tctosec(tc, fps)      - TC to seconds
$regext(str, pattern [, array]) - Regex extract
$abs(num)              - Absolute value
$log(num)              - Natural log
$random(min, max)      - Random integer
$hex(int)              - To hex
$dec(hex)              - To decimal
$guid()                - Random GUID
$base64(str)           - Base64 encode
$base64dec(str)        - Base64 decode
$urlencode(str)        - URL encode
$jsonencode(str)       - JSON encode
$readarray(arr, idx [, zero_based]) - Array element
$week([y, m, d])       - Week number
$weekday([y, m, d])    - Week day
$lookup(ref, table, search) - Lookup table
$lookuprep(ref, table, search) - Lookup replace
$sort(arr [, sep])     - Sort array
$count(str, search)    - Count occurrences
$foreach(arr, op)      - Iterate array
$stringf(fmt, args)    - Printf-style format
$fsize(path)           - File size
$fext(path)            - File extension
$fname(path)           - File name
$fpath(path)           - File directory
$fdrive(path)          - File drive
$asplit(arr [, sep])   - Array to string
$ffconcat(arr)         - FFmpeg concat format
$owner(path)           - File owner
$waccess(path)         - Write access check
$dateweek(y, w, d [, start]) - Date from week
$timecalc(unit, amount, datetime) - Time calculation
$shortcut(path)        - Parse shortcut/alias
$jsonget(json, path)   - Get JSON value
$jsonput(json, path, value) - Set JSON value
$xxhash(path)          - File hash (8 char)
$xxhash64(path)        - File hash (16 char)
```

## 3. Node Types

### 3.1 Monitors
**mon_folder** - Folder monitoring
- path, accept_filter, deny_filter, deny_folders, deny_attributes
- create_folder, recurse, localize_file
- check_growing (once/continuously), skip_verification
- forget_missing, limit_file_size, rebuild_history, clear_history

**mon_ftp** - FTP monitoring (same as folder but FTP)
**mon_sequence** - Image sequence detection
**mon_p2** - Panasonic P2 camera structure
**mon_xf** - Canon XF camera structure
**mon_gopro** - GoPro camera structure

### 3.2 Decoders
**dec_avmedia** - AviSynth+ media decoder
- use_video, video_decode (none/intelligent/full)
- force_video_format, use_audio, audio_decode
- force_channels, bit_depth, sample_rate
- use_x64_avisynth, force_8bit, non_linear_seek

**dec_stills** - Stills to video
**dec_youtube** - YouTube/video URL decoder (yt-dlp)

### 3.3 Encoders
**enc_av_mp4** - H.264/MP4
- video_size (WxH), display_aspect, pixel_aspect
- resize_method (stretch/fit/fill), video_range
- color_space, lut_tone_mapping, framerate
- interlaced_input, field_order, video_bitrate
- level, profile, tune, quality_speed
- force_420_8bit, faststart, wrapper
- audio: discrete_tracks, total_channels, format, bitrate, sample_rate, conform_volume
- custom_x264_options

**enc_av_265** - H.265/HEVC (same params as MP4 + HDR support)
**enc_av_prores** - Apple ProRes (format, profile, processing mode)
**enc_av_dnxhd** - Avid DNxHD
**enc_av_dnxhr** - Avid DNxHR
**enc_av_xdcamhd** - Sony XDCAM HD
**enc_av_avcintra** - Panasonic AVC-Intra
**enc_av_av1** - AV1
**enc_av_mpeg** - MPEG-2
**enc_av_uncompressed** - Uncompressed
**enc_av_wm** - Windows Media
**enc_av_xavc** - Sony XAVC
**enc_av_imxd10** - Sony IMX/D-10
**enc_av_dv** - DV
**enc_av_dvd** - DVD
**enc_av_customff** - Custom FFmpeg arguments
**enc_a_audio** - Audio-only encoding

### 3.4 Filters (AviSynth+ on Linux via FFmpeg filters)
**avs_v_resize** - Video resize
**avs_v_crop** - Video crop
**avs_v_color** - Color correction
**avs_v_watermark** - Watermark overlay
**avs_v_tc** - Timecode burn-in
**avs_v_deinterlace** - Deinterlace
**avs_v_pad** - Add padding
**avs_v_flip** - Flip
**avs_v_fpsconv** - Frame rate conversion
**avs_v_linear_trans** - Linear transform
**avs_v_safecolorlimiter** - Safe color limiter
**avs_v_swapfields** - Swap fields
**avs_v_videolayer** - Video layer
**avs_av_fade** - Audio/video fade
**avs_av_insertmedia** - Insert media
**avs_v_reverse** - Reverse video
**avs_a_normalize** - Audio normalize
**avs_a_acmapper** - Audio channel mapper

### 3.5 Operators
**op_cond** - Conditional evaluation
- 8 expression rows with And/Or logic
- Operators: =, ==, ≠, >, <, ≥, ≤
- Wildcards (*, ?) in string comparisons
- Dispel on false option

**op_populate** - Set user variables
- 8 variable assignment rows
- Supports math expressions: %var% * 10
- JSON dot notation: .foo.bar=value

**op_analyzer** - File/media analysis
**op_foreach** - Loop iteration
**op_hold** - Delay execution
**sub_wf** - Sub-workflow

### 3.6 Utilities
**cmd_run** - Shell command execution
- Full command with variable support
- stdout/stderr capture to variable
- Timeout, exit code handling
- Set %s_source% on completion

**other_email** - Email notification
**other_httpsend** - HTTP request
**other_textfile** - Write text file
**dest_folder** - Folder delivery
- prefix, suffix, overwrite, unique_name
- zero_padding, drop_original_name, drop_extension
- move_instead_of_copy, force_case
**dest_ftp** - FTP delivery
**dest_mediadist** - Media distribution

## 4. Workflow Properties
- description, work_folder, workflow_id
- sleep_timer (seconds), cron (schedule notation)
- priority (0-5), timeout_level
- active_on (days of week)

## 5. Host System
- Host groups (max 255)
- Local/global shared media cache
- CPU roof (min available CPU before new job)
- Max jobs per priority class
- REST service (port, enable)
- Passive mode (manage only, no processing)

## 6. Job System
- Priority classes (0-5, higher = more priority)
- Per-priority-class max jobs
- Job splitting across nodes
- Pause/resume/abort/retry
- Timeout detection
- Job variables (populated during execution)

## 7. REST API (must be compatible with original)
```
GET    /api/workflows
GET    /api/workflows/status
POST   /api/workflows (import)
PUT    /api/workflows/{id}
PUT    /api/workflows/{id}/state
DELETE /api/workflows/{id}
GET    /api/workflows/{id}/user_variables
GET    /api/user_variables
POST   /api/user_variables (import)
GET    /api/jobs
GET    /api/jobs/active
GET    /api/jobs/{id}
POST   /api/jobs (submit)
PUT    /api/jobs/{id} (pause/resume/abort/retry)
DELETE /api/jobs/{id} (abort)
GET    /api/joblog/{id}
GET    /api/jobvars/{id}
GET    /api/history
GET    /api/presets
POST   /api/presets/import
GET    /api/nodes/available
```

## 8. Docker/Kubernetes Architecture
- Master node: API + Web GUI + Scheduler
- Worker nodes: Process jobs assigned by master
- Shared storage: NFS/PVC for media cache
- Health checks: HTTP endpoints
- Horizontal scaling: Add worker pods
- Priority-based scheduling across farm
