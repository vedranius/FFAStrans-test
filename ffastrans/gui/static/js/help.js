const HelpSystem = {
    nodeDescriptions: {
        mon_folder: 'Watches a folder for new files. Automatically detects when files appear and triggers workflow processing. Supports accept/deny filters, growing file detection, and recursive monitoring.',
        mon_sequence: 'Detects and assembles image sequences (DPX, EXR, TIFF) into video streams. Configurable frame range and pattern.',
        dec_avmedia: 'Probes media files using FFprobe to extract video/audio metadata (codec, resolution, bitrate, duration). Sets variables for downstream nodes.',
        dec_stills: 'Converts still image sequences into video clips with configurable frame rate and duration.',
        dec_youtube: 'Downloads videos from YouTube and other platforms using yt-dlp. Supports quality selection and format options.',
        enc_av_mp4: 'Encodes video to H.264/MP4 with full control over bitrate, CRF, profile, level, pixel format, and audio encoding. Supports resize, deinterlace, and faststart.',
        enc_av_265: 'Encodes video to H.265/HEVC with HDR support. Efficient compression for 4K/UHD content with customizable presets.',
        enc_av_prores: 'Encodes to Apple ProRes for professional post-production. Profiles: Proxy, LT, 422, HQ, 4444, 4444 XQ.',
        enc_av_dnxhr: 'Encodes to Avid DNxHR for cross-platform editing. Profiles: LB, SQ, HQ, HQX, 444.',
        enc_av_dnxhd: 'Encodes to Avid DNxHD for HD workflows. Fixed bitrate profiles for broadcast compatibility.',
        enc_av_xdcamhd: 'Encodes to Sony XDCAM HD for broadcast delivery. MXF wrapper with professional audio support.',
        enc_av_av1: 'Encodes to AV1 for next-generation web streaming. Superior compression vs H.265.',
        enc_av_customff: 'Run custom FFmpeg command with full control over all encoding parameters. Use for advanced or unsupported formats.',
        enc_a_audio: 'Audio-only encoding. Extract and encode audio to PCM, AAC, MP3, FLAC with channel/sample rate control.',
        avs_v_resize: 'Resize video frames. Algorithms: Lanczos (sharp), Bilinear (smooth), Bicubic (balanced). Supports stretch/fit/fill modes.',
        avs_v_crop: 'Crop video frames to remove unwanted areas. Pixel-precise X/Y/Width/Height control.',
        avs_v_color: 'Adjust video color properties: brightness, contrast, saturation, gamma. Useful for color correction.',
        avs_v_watermark: 'Overlay image watermark on video. Position: corners, center. Supports PNG transparency.',
        avs_v_tc: 'Burn timecode or custom text onto video. Dynamic variables supported. Configurable font, size, color, position.',
        avs_v_deinterlace: 'Remove interlacing artifacts from interlaced video sources. Bob (motion) or Weave (field) modes.',
        avs_v_pad: 'Add padding/borders around video. Useful for aspect ratio conversion or letterboxing.',
        avs_v_flip: 'Flip video horizontally or vertically. Useful for mirrored footage or creative effects.',
        avs_v_fpsconv: 'Convert frame rates with motion-compensated interpolation (MCI), frame blending, or direct drop/dup.',
        avs_v_reverse: 'Reverse video playback order. Process entire clip in reverse.',
        avs_av_fade: 'Apply audio/video fade in or out at specified time with configurable duration.',
        op_cond: 'Conditional logic node. Evaluate up to 8 expressions with AND/OR logic. Route workflow based on variable values, file properties, or custom conditions.',
        op_populate: 'Set or modify workflow variables. Up to 8 assignments per node. Supports math expressions and variable interpolation.',
        op_analyzer: 'Deep file analysis using FFprobe. Extracts detailed stream information, codec profiles, color metadata.',
        op_foreach: 'Loop iteration over items. Process arrays, file lists, or comma-separated values one by one.',
        op_hold: 'Pause workflow execution for specified seconds. Useful for timing control or waiting for external processes.',
        cmd_run: 'Execute shell command on the server. Full variable support in command. Captures stdout/stderr to variables.',
        other_email: 'Send email notification via SMTP. Useful for job completion alerts or error notifications.',
        other_httpsend: 'Make HTTP/REST API calls. Supports GET, POST, PUT, DELETE with JSON body. Integrates with external systems.',
        other_textfile: 'Write content to text file. Supports overwrite or append mode. Dynamic variables in content.',
        dest_folder: 'Deliver processed file to destination folder. Options: prefix/suffix, overwrite, unique naming, move vs copy, case conversion.',
    },
    variableReference: {
        'File Variables': {
            '%s_source%': 'Current input file path',
            '%s_original_full%': 'Full original file path',
            '%s_original_path%': 'Directory of input file',
            '%s_original_name%': 'File name without extension',
            '%s_original_ext%': 'File extension (with dot)',
        },
        'Media Variables': {
            '%i_width%': 'Video width in pixels',
            '%i_height%': 'Video height in pixels',
            '%f_fps%': 'Frame rate (float)',
            '%s_v_codec%': 'Video codec name',
            '%s_a_codec%': 'Audio codec name',
            '%i_v_bitrate%': 'Video bitrate',
            '%i_a_bitrate%': 'Audio bitrate',
            '%f_duration%': 'Duration in seconds',
        },
        'Time Variables': {
            '%s_date%': 'Current date (YYYY-MM-DD)',
            '%s_time%': 'Current time (HH:MM:SS)',
            '%i_year%': 'Current year',
            '%i_month%': 'Current month (1-12)',
            '%i_day%': 'Current day (1-31)',
        },
        'System Variables': {
            '%s_hostname%': 'Server hostname',
            '%s_wf_name%': 'Workflow name',
            '%s_wf_id%': 'Workflow ID',
            '%s_node_name%': 'Current node name',
            '%s_job_id%': 'Current job ID',
        },
    },
    functionReference: [
        {name:'$replace', syntax:'$replace(str, find, replace)', desc:'Replace occurrences in string'},
        {name:'$upper', syntax:'$upper(str)', desc:'Convert to uppercase'},
        {name:'$lower', syntax:'$lower(str)', desc:'Convert to lowercase'},
        {name:'$length', syntax:'$length(str)', desc:'Get string length'},
        {name:'$round', syntax:'$round(num [, dec])', desc:'Round number'},
        {name:'$random', syntax:'$random(min, max)', desc:'Random integer in range'},
        {name:'$guid', syntax:'$guid()', desc:'Generate random GUID'},
        {name:'$fsize', syntax:'$fsize(path)', desc:'Get file size in bytes'},
        {name:'$fext', syntax:'$fext(path)', desc:'Get file extension'},
        {name:'$fname', syntax:'$fname(path)', desc:'Get file name without extension'},
        {name:'$fpath', syntax:'$fpath(path)', desc:'Get directory path'},
        {name:'$jsonget', syntax:'$jsonget(json, path)', desc:'Get value from JSON'},
        {name:'$regreplace', syntax:'$regreplace(str, pattern, replace)', desc:'Regex replace'},
        {name:'$between', syntax:'$between(str, from, to)', desc:'Extract substring between markers'},
        {name:'$base64', syntax:'$base64(str)', desc:'Base64 encode'},
        {name:'$base64dec', syntax:'$base64dec(str)', desc:'Base64 decode'},
        {name:'$read', syntax:'$read(path)', desc:'Read file contents'},
        {name:'$exists', syntax:'$exists(path)', desc:'Check if file/folder exists'},
        {name:'$xxhash', syntax:'$xxhash(path)', desc:'File hash (8 char)'},
    ],
    showNodeHelp(nodeType) {
        const desc = this.nodeDescriptions[nodeType] || 'No description available.';
        Toast.info(desc, 8000);
    },
    showVariableRef() {
        let html = '<div class="help-panel"><h3>Variable Reference</h3>';
        for (const [category, vars] of Object.entries(this.variableReference)) {
            html += `<h4>${category}</h4><table class="help-table">`;
            for (const [varName, desc] of Object.entries(vars)) {
                html += `<tr><td><code>${varName}</code></td><td>${desc}</td></tr>`;
            }
            html += '</table>';
        }
        html += '<h4>Functions</h4><table class="help-table">';
        this.functionReference.forEach(fn => {
            html += `<tr><td><code>${fn.syntax}</code></td><td>${fn.desc}</td></tr>`;
        });
        html += '</table></div>';
        this.showPanel('Variable & Function Reference', html);
    },
    showQuickStart() {
        const html = `<div class="help-panel">
            <h3>Quick Start Guide</h3>
            <div class="guide-step"><span class="step-num">1</span><div><strong>Create a Workflow</strong><p>Go to Workflows → "+ New Workflow" to create your first transcoding pipeline.</p></div></div>
            <div class="guide-step"><span class="step-num">2</span><div><strong>Add Nodes</strong><p>Drag nodes from the left palette onto the canvas. Start with a monitor or decoder node.</p></div></div>
            <div class="guide-step"><span class="step-num">3</span><div><strong>Connect Nodes</strong><p>Click an output port (green circle) and drag to an input port (red circle) to create connections.</p></div></div>
            <div class="guide-step"><span class="step-num">4</span><div><strong>Configure Properties</strong><p>Click any node to edit its properties in the right panel. Set output format, quality, etc.</p></div></div>
            <div class="guide-step"><span class="step-num">5</span><div><strong>Submit a Job</strong><p>Click "Run Job" or drag a file onto a decoder node to start processing.</p></div></div>
            <div class="guide-step"><span class="step-num">6</span><div><strong>Monitor Progress</strong><p>Watch real-time progress on the Dashboard or Monitor page. View logs for debugging.</p></div></div>
            <h4>Common Workflows</h4>
            <ul class="guide-list">
                <li><strong>Simple Transcode:</strong> Folder Monitor → H.264 Encoder → Destination Folder</li>
                <li><strong>Multi-Output:</strong> Folder Monitor → Split → H.264 + ProRes + DNxHR</li>
                <li><strong>Batch Process:</strong> Folder Monitor → Condition → Populate → Encoder → Destination</li>
                <li><strong>YouTube Download:</strong> YouTube Decoder → H.264 Encoder → Destination Folder</li>
            </ul>
        </div>`;
        this.showPanel('Quick Start Guide', html);
    },
    showPanel(title, html) {
        const overlay = document.createElement('div');
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:600;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';
        const panel = document.createElement('div');
        panel.style.cssText = 'background:var(--bg-secondary);border:1px solid var(--border);border-radius:12px;width:90%;max-width:700px;max-height:80vh;overflow-y:auto;padding:24px;';
        panel.innerHTML = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px"><h2 style="margin:0;font-size:1.1em">${title}</h2><button class="modal-close" onclick="this.closest('div[style]').remove()" style="background:none;border:none;color:var(--text-secondary);font-size:1.5em;cursor:pointer">&times;</button></div>${html}`;
        overlay.appendChild(panel);
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
    },
};
