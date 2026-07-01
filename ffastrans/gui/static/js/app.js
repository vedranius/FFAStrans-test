let editor = null;
let currentSection = 'dashboard';
let allWorkflows = [];
let logCollapsed = false;
let logCount = 0;

function addLogEntry(msg, type) {
    const body = document.getElementById('activity-log-body');
    if (!body) return;
    const line = document.createElement('div');
    line.className = 'activity-log-line activity-log-' + (type || 'info');
    const time = new Date().toLocaleTimeString();
    line.innerHTML = `<span class="activity-log-time">${time}</span>${msg}`;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
    logCount++;
    const countEl = document.getElementById('log-count');
    if (countEl) countEl.textContent = logCount;
    if (body.children.length > 200) body.removeChild(body.firstChild);
}

function toggleActivityLog() {
    const body = document.getElementById('activity-log-body');
    logCollapsed = !logCollapsed;
    body.classList.toggle('collapsed', logCollapsed);
}

function clearActivityLog() {
    const body = document.getElementById('activity-log-body');
    body.innerHTML = '';
    logCount = 0;
    document.getElementById('log-count').textContent = '0';
    addLogEntry('Log cleared', 'info');
}

document.addEventListener('DOMContentLoaded', () => {
    showSection('dashboard');
    loadDashboard();
    loadNodePalette();
    ws.connect();
    ws.on('connected', () => {
        document.getElementById('ws-status').className = 'status-dot connected';
        addLogEntry('Connected to server', 'success');
    });
    ws.on('disconnected', () => {
        document.getElementById('ws-status').className = 'status-dot disconnected';
        addLogEntry('Disconnected from server', 'warn');
    });
    ws.on('jobs_update', (data) => {
        if (currentSection === 'dashboard') updateJobsTable(data);
        if (currentSection === 'monitor') updateMonitorRunning(data);
    });
    ws.on('job_completed', (data) => {
        addLogEntry('Job completed: ' + (data.job_id||'').substr(0,8), 'success');
        Toast.success('Job completed');
        loadDashboard();
    });
    ws.on('job_failed', (data) => {
        addLogEntry('Job failed: ' + (data.job_id||'').substr(0,8), 'error');
        Toast.error('Job failed');
        loadDashboard();
    });
    ws.on('server_log', (data) => {
        addLogEntry(data.message || JSON.stringify(data), data.level || 'info');
    });

    const origFetch = window.fetch;
    window.fetch = function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
        const method = args[1]?.method || 'GET';
        if (url.startsWith('/api/')) {
            const short = url.replace('/api/', '');
            addLogEntry(`${method} /${short}`, 'api');
        }
        return origFetch.apply(this, args).then(resp => {
            if (url.startsWith('/api/') && !resp.ok) {
                addLogEntry(`ERROR ${resp.status} ${url}`, 'error');
            }
            return resp;
        }).catch(e => {
            if (url.startsWith('/api/')) addLogEntry(`FAILED ${url}: ${e.message}`, 'error');
            throw e;
        });
    };

    setInterval(loadDashboard, 10000);
    setInterval(() => fetch('/api/hosts/heartbeat').catch(() => {}), 15000);
    addLogEntry('Dashboard loaded', 'info');
});

function showSection(id) {
    currentSection = id;
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
    document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
    document.querySelectorAll('nav a').forEach(a => {
        if ((id === 'dashboard' && a.textContent === 'Dashboard') ||
            (id === 'workflows' && a.textContent === 'Workflows') ||
            (id === 'monitor' && a.textContent === 'Monitor') ||
            (id === 'nodes' && a.textContent === 'Nodes') ||
            (id === 'settings' && a.textContent === 'Settings')) {
            a.classList.add('active');
        }
    });
    if (id === 'dashboard') loadDashboard();
    if (id === 'workflows') loadWorkflowList();
    if (id === 'monitor') loadMonitor();
    if (id === 'nodes') loadWorkers();
    if (id === 'settings') loadAllSettings();
}

async function loadMonitor() {
    try {
        const jobs = await API.getActiveJobs().catch(() => []);
        updateMonitorRunning(jobs);
        refreshLogJobs();
    } catch(e) {}
}

async function loadDashboard() {
    try {
        const [jobs, wfs, hist, hosts] = await Promise.all([
            API.getActiveJobs().catch(() => []),
            API.getWorkflows().catch(() => []),
            API.getHistory(0, 50).catch(() => []),
            API.getHosts().catch(() => []),
        ]);
        const running = jobs.filter(j => j.state === 'running').length;
        const queued = jobs.filter(j => j.state === 'queued').length;
        document.getElementById('stat-running').textContent = running;
        document.getElementById('stat-queued').textContent = queued;
        document.getElementById('stat-completed').textContent = hist.filter(h => h.state === 'completed').length;
        document.getElementById('stat-failed').textContent = hist.filter(h => h.state === 'failed').length;
        document.getElementById('stat-workflows').textContent = wfs.length;
        document.getElementById('stat-workers').textContent = hosts.length;
        updateJobsTable(jobs);
        updateHistoryTable(hist);
    } catch(e) { console.error('Dashboard error:', e); }
}

function updateJobsTable(jobs) {
    const tbody = document.querySelector('#active-jobs-table tbody');
    if (!jobs || jobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#555;padding:30px">No active jobs</td></tr>';
        return;
    }
    tbody.innerHTML = jobs.map(j => `<tr>
        <td style="font-family:monospace;font-size:.8em">${j.id.substr(0,8)}</td>
        <td>${j.wf_id}</td>
        <td title="${j.input_file||''}">${(j.input_file||'').split('/').pop()||'-'}</td>
        <td><span class="state-badge state-${j.state}">${j.state}</span></td>
        <td><div class="progress-bar" style="width:120px"><div class="progress-fill" style="width:${j.total_progress}%"></div></div><span style="font-size:.75em;color:var(--text-secondary)">${Math.round(j.total_progress)}%</span></td>
        <td>
            <button class="btn btn-xs btn-danger" onclick="abortJob('${j.id}')">Abort</button>
            <button class="btn btn-xs" onclick="viewJobLog('${j.id}')">Log</button>
        </td>
    </tr>`).join('');
}

function updateHistoryTable(hist) {
    const tbody = document.querySelector('#history-table tbody');
    if (!hist || hist.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#555;padding:30px">No history yet</td></tr>';
        return;
    }
    tbody.innerHTML = hist.slice(0, 20).map(h => {
        const dur = h.finished_at && h.started_at ? Math.round(h.finished_at - h.started_at) + 's' : '-';
        const outFile = h.output_file || '';
        const dlBtn = outFile ? `<button class="btn btn-xs" onclick="downloadFile('${outFile.replace(/'/g, "\\'")}')" title="Download output">&#8686;</button>` : '';
        return `<tr>
            <td>${new Date(h.started_at*1000).toLocaleTimeString()}</td>
            <td>${h.wf_name||h.wf_id}</td>
            <td title="${h.input_file||''}">${(h.input_file||'').split('/').pop()||'-'}</td>
            <td><span class="state-badge state-${h.state}">${h.state}</span></td>
            <td>${dur}</td>
            <td><button class="btn btn-xs" onclick="viewJobLog('${h.id}')">Log</button> ${dlBtn}</td>
        </tr>`;
    }).join('');
}

function downloadFile(path) {
    window.open('/api/files/download?path=' + encodeURIComponent(path), '_blank');
}

function updateMonitorRunning(jobs) {
    const tbody = document.querySelector('#monitor-running-table tbody');
    if (!jobs || jobs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#555;padding:30px">No running jobs</td></tr>';
        return;
    }
    tbody.innerHTML = jobs.map(j => `<tr>
        <td>${j.wf_id}</td>
        <td title="${j.input_file||''}">${(j.input_file||'').split('/').pop()||'-'}</td>
        <td>${(j.splits||[]).map(s=>s.current_node).join(', ')||'-'}</td>
        <td><span class="state-badge state-${j.state}">${j.state}</span></td>
        <td><div class="progress-bar" style="width:150px"><div class="progress-fill" style="width:${j.total_progress}%"></div></div><span style="font-size:.75em;color:var(--text-secondary)">${Math.round(j.total_progress)}%</span></td>
        <td>
            <button class="btn btn-xs btn-danger" onclick="abortJob('${j.id}')">Abort</button>
            <button class="btn btn-xs" onclick="pauseJob('${j.id}')">Pause</button>
        </td>
    </tr>`).join('');
}

async function abortJob(id) {
    try { await API.jobAction(id, 'abort'); Toast.info('Job aborted'); loadDashboard(); } catch(e) { Toast.error('Error: ' + e.message); }
}

async function pauseJob(id) {
    try { await API.jobAction(id, 'pause'); Toast.info('Job paused'); } catch(e) { Toast.error('Error: ' + e.message); }
}

function viewJobLog(jobId) {
    showSection('monitor');
    showMonitorTab('logs');
    refreshLogJobs();
    setTimeout(() => { document.getElementById('log-job-select').value = jobId; loadJobLog(jobId); }, 500);
}

function showMonitorTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => {
        if (b.textContent.toLowerCase().includes(tab === 'running' ? 'running' : tab)) b.classList.add('active');
    });
    document.getElementById('monitor-' + tab).classList.add('active');
    if (tab === 'history') loadMonitorHistory();
    if (tab === 'logs') refreshLogJobs();
}

async function loadMonitorHistory() {
    try {
        const hist = await API.getHistory(0, 100);
        const tbody = document.querySelector('#monitor-history-table tbody');
        tbody.innerHTML = hist.map(h => {
            const dur = h.finished_at && h.started_at ? Math.round(h.finished_at - h.started_at) + 's' : '-';
            return `<tr>
                <td>${new Date(h.started_at*1000).toLocaleString()}</td>
                <td>${h.wf_name||h.wf_id}</td>
                <td>${(h.input_file||'').split('/').pop()||'-'}</td>
                <td><span class="state-badge state-${h.state}">${h.state}</span></td>
                <td>${dur}</td>
                <td><button class="btn btn-xs" onclick="viewJobLog('${h.id}')">Log</button></td>
            </tr>`;
        }).join('');
    } catch(e) {}
}

function filterHistory(query) {
    const rows = document.querySelectorAll('#monitor-history-table tbody tr');
    rows.forEach(r => { r.style.display = r.textContent.toLowerCase().includes(query.toLowerCase()) ? '' : 'none'; });
}

async function refreshLogJobs() {
    try {
        const jobs = await API.getJobs();
        const sel = document.getElementById('log-job-select');
        const current = sel.value;
        sel.innerHTML = '<option value="">Select a job...</option>' +
            jobs.map(j => `<option value="${j.id}">${j.id.substr(0,8)} - ${(j.input_file||'').split('/').pop()||'unknown'} [${j.state}]</option>`).join('');
        if (current) sel.value = current;
    } catch(e) {}
}

async function loadJobLog(jobId) {
    if (!jobId) { document.getElementById('job-log-content').textContent = 'Select a job to view its log.'; return; }
    try {
        const log = await API.getJobLog(jobId);
        const el = document.getElementById('job-log-content');
        if (!log || log.length === 0) { el.textContent = 'No log entries for this job.'; return; }
        el.innerHTML = log.map(line => {
            let cls = '';
            if (line.toLowerCase().includes('error')) cls = 'log-error';
            else if (line.toLowerCase().includes('warn')) cls = 'log-warn';
            else if (line.toLowerCase().includes('success') || line.toLowerCase().includes('completed')) cls = 'log-success';
            else if (line.toLowerCase().includes('info')) cls = 'log-info';
            return `<div class="log-line ${cls}">${line}</div>`;
        }).join('');
        el.scrollTop = el.scrollHeight;
    } catch(e) { document.getElementById('job-log-content').textContent = 'Error loading log.'; }
}

function loadNodePalette() {
    API.getNodes().then(categories => {
        const content = document.getElementById('palette-content');
        if (!content) return;
        let html = '';
        const catColors = {Monitor:'#2196f3',Decoder:'#ff9800',Encoder:'#4caf50',Filter:'#9c27b0',Operator:'#f44336',Command:'#ff5722',Utility:'#795548',Destination:'#00bcd4'};
        for (const [cat, nodes] of Object.entries(categories)) {
            html += `<div class="palette-category" data-cat="${cat}"><h4>${cat}</h4>`;
            for (const n of nodes) {
                const desc = HelpSystem.nodeDescriptions[n.type] || '';
                html += `<div class="palette-item" draggable="true" data-type="${n.type}" data-name="${n.name}" title="${n.name}: ${desc}"><span class="palette-dot" style="background:${catColors[cat]||'#666'}"></span><span>${n.name}</span></div>`;
            }
            html += '</div>';
        }
        content.innerHTML = html;
        content.querySelectorAll('.palette-item').forEach(item => {
            item.addEventListener('dragstart', e => {
                e.dataTransfer.setData('text/plain', item.dataset.type);
                e.dataTransfer.setData('application/name', item.dataset.name);
            });
        });
    });
}

function filterNodePalette(query) {
    const q = query.toLowerCase();
    document.querySelectorAll('.palette-item').forEach(item => {
        const name = (item.dataset.name || '').toLowerCase();
        const type = (item.dataset.type || '').toLowerCase();
        item.style.display = (!q || name.includes(q) || type.includes(q)) ? '' : 'none';
    });
}

async function loadWorkflowList() {
    try {
        const wfs = await API.getWorkflows();
        allWorkflows = wfs;
        renderWorkflowList(wfs);
    } catch(e) { document.getElementById('workflow-list').innerHTML = '<p style="color:red">Error loading workflows</p>'; }
}

function renderWorkflowList(wfs) {
    const list = document.getElementById('workflow-list');
    if (wfs.length === 0) {
        list.innerHTML = '<div class="panel" style="text-align:center;padding:40px;color:#555"><h3>No workflows yet</h3><p>Click "+ New Workflow" to create your first transcoding pipeline.</p></div>';
        return;
    }
    list.innerHTML = wfs.map(wf => `
        <div class="workflow-card" onclick="openWorkflow('${wf.id}')">
            <div class="wf-info">
                <h3>${wf.name}</h3>
                <p>ID: ${wf.id} | Nodes: ${(wf.nodes||[]).length} | State: <span class="state-badge state-${wf.state}">${wf.state}</span></p>
            </div>
            <div class="wf-actions">
                <button class="btn btn-sm" onclick="event.stopPropagation();exportWorkflow('${wf.id}')">&#8686; Export</button>
                <button class="btn btn-sm" onclick="event.stopPropagation();toggleWorkflow('${wf.id}','${wf.state}')">${wf.state==='stopped'||wf.state==='disabled'?'Start':'Stop'}</button>
                <button class="btn btn-sm btn-success" onclick="event.stopPropagation();submitToWorkflow('${wf.id}')">Run</button>
                <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();deleteWorkflow('${wf.id}')">Delete</button>
            </div>
        </div>
    `).join('');
}

async function exportWorkflow(id) {
    try {
        const wf = await API.getWorkflow(id);
        const json = JSON.stringify(wf, null, 2);
        const blob = new Blob([json], {type: 'application/json'});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (wf.name || 'workflow').replace(/[^a-z0-9]/gi, '_') + '.json';
        a.click();
        URL.revokeObjectURL(url);
        Toast.success('Workflow exported');
    } catch(e) { Toast.error('Export failed: ' + e.message); }
}

function filterWorkflows(query) {
    const q = query.toLowerCase();
    const filtered = allWorkflows.filter(wf => wf.name.toLowerCase().includes(q) || wf.id.toLowerCase().includes(q));
    renderWorkflowList(filtered);
}

function createNewWorkflow() {
    showModal('New Workflow', `
        <div class="form-group"><label>Workflow Name</label><input type="text" id="modal-wf-name" value="New Workflow"></div>
        <div class="form-group"><label>Description (optional)</label><textarea id="modal-wf-desc" rows="2" placeholder="Describe what this workflow does..."></textarea></div>
        <button class="btn btn-primary" onclick="doCreateWorkflow()">Create</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
    setTimeout(() => document.getElementById('modal-wf-name').focus(), 100);
}

async function doCreateWorkflow() {
    const name = document.getElementById('modal-wf-name').value.trim();
    const desc = document.getElementById('modal-wf-desc')?.value.trim() || '';
    if (!name) return;
    closeModal();
    try {
        const wf = await API.createWorkflow({name, description: desc, nodes:[], connections:[], variables:[]});
        Toast.success('Workflow created');
        openWorkflow(wf.id);
    } catch(e) { Toast.error('Error: ' + e.message); }
}

async function importWorkflow() {
    showModal('Import Workflow', `
        <div class="form-group"><label>Paste workflow JSON</label><textarea id="modal-wf-json" rows="10" style="width:100%;font-family:monospace;font-size:.8em" placeholder='{"name":"My Workflow","nodes":[...],"connections":[...]}'></textarea></div>
        <div style="display:flex;gap:8px"><button class="btn btn-primary" onclick="doImportWorkflow()">Import</button><button class="btn" onclick="closeModal()">Cancel</button></div>
    `);
}

async function doImportWorkflow() {
    const json = document.getElementById('modal-wf-json').value;
    if (!json.trim()) return;
    try {
        const data = JSON.parse(json);
        await API.post('/workflows/import', data);
        closeModal();
        Toast.success('Workflow imported');
        loadWorkflowList();
    } catch(e) { Toast.error('Invalid JSON: ' + e.message); }
}

async function openWorkflow(id) {
    try {
        const wf = await API.getWorkflow(id);
        document.getElementById('workflow-list').style.display = 'none';
        document.querySelector('#workflows .toolbar').style.display = 'none';
        document.getElementById('wf-editor').style.display = 'block';
        document.getElementById('editor-wf-name').textContent = wf.name + ' (ID: ' + wf.id + ')';
        if (!editor) editor = new WorkflowEditor('wf-canvas');
        editor.loadWorkflow(wf);
        loadNodePalette();
        setTimeout(() => {
            const container = document.getElementById('canvas-container');
            const canvas = document.getElementById('wf-canvas');
            if (container && canvas) {
                canvas.width = container.clientWidth || 800;
                canvas.height = container.clientHeight || 600;
                editor.resize();
                editor.draw();
            }
        }, 100);
    } catch(e) { Toast.error('Error: ' + e.message); }
}

function closeEditor() {
    document.getElementById('wf-editor').style.display = 'none';
    document.getElementById('workflow-list').style.display = 'block';
    document.querySelector('#workflows .toolbar').style.display = 'flex';
    loadWorkflowList();
}

function hidePropertiesBar() {
    if (editor) editor.hidePropertiesBar();
}

async function saveWorkflow() {
    if (!editor || !editor.workflowId) return;
    try {
        const data = editor.toJSON();
        await API.updateWorkflow(editor.workflowId, data);
        Toast.success('Workflow saved');
    } catch(e) { Toast.error('Error: ' + e.message); }
}

function showSubmitJobModal(prefillPath) {
    showModal('Submit Job', `
        <div class="form-group"><label>Input File Path</label>
            <div style="display:flex;gap:6px"><input type="text" id="modal-job-file" value="${prefillPath||''}" placeholder="/path/to/file.mp4" style="flex:1">
            <button class="btn btn-sm" onclick="FileBrowser.open({mode:'select',onSelect:p=>document.getElementById('modal-job-file').value=p})">Browse</button></div>
            <div class="help-text">Enter the full path to the file, or use Browse to navigate.</div>
        </div>
        <div class="form-group"><label>Workflow</label>
            <select id="modal-job-wf" style="width:100%;padding:8px;border:1px solid var(--border);border-radius:4px;background:var(--bg-tertiary);color:var(--text-primary)"></select>
        </div>
        <button class="btn btn-success" onclick="doShowSubmitJob()">Submit Job</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
    API.getWorkflows().then(wfs => {
        const sel = document.getElementById('modal-job-wf');
        if (sel) sel.innerHTML = wfs.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    });
}

async function doShowSubmitJob() {
    const file = document.getElementById('modal-job-file').value;
    const wfId = document.getElementById('modal-job-wf').value;
    closeModal();
    try {
        const result = await API.submitJob({wf_id: wfId, inputfile: file});
        Toast.success('Job submitted: ' + result.job_id.substr(0,8));
    } catch(e) { Toast.error('Error: ' + e.message); }
}

async function runWorkflow() {
    if (!editor || !editor.workflowId) return;
    showModal('Submit Job', `
        <div class="form-group"><label>Input File Path</label>
            <div style="display:flex;gap:6px"><input type="text" id="modal-job-file" value="" placeholder="/path/to/file.mp4" style="flex:1">
            <button class="btn btn-sm" onclick="FileBrowser.open({mode:'select',onSelect:p=>document.getElementById('modal-job-file').value=p})">Browse</button></div>
            <div class="help-text">Leave empty if workflow uses a monitor node.</div>
        </div>
        <button class="btn btn-success" onclick="doRunWorkflow()">Submit</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doRunWorkflow() {
    const file = document.getElementById('modal-job-file').value;
    closeModal();
    try {
        const result = await API.submitJob({wf_id: editor.workflowId, inputfile: file});
        Toast.success('Job submitted: ' + result.job_id.substr(0,8));
    } catch(e) { Toast.error('Error: ' + e.message); }
}

function runWorkflowUpload() {
    if (!editor || !editor.workflowId) return;
    FileBrowser.open({
        mode: 'upload',
        title: 'Upload File & Submit Job',
        onSelect: async (path) => {
            try {
                const result = await API.submitJob({wf_id: editor.workflowId, inputfile: path});
                Toast.success('Job submitted: ' + result.job_id.substr(0,8));
            } catch(e) { Toast.error('Error: ' + e.message); }
        }
    });
}

async function submitToWorkflow(id) {
    showModal('Submit Job', `
        <div class="form-group"><label>Input File Path</label>
            <div style="display:flex;gap:6px"><input type="text" id="modal-job-file" value="" placeholder="/path/to/file.mp4" style="flex:1">
            <button class="btn btn-sm" onclick="FileBrowser.open({mode:'select',onSelect:p=>document.getElementById('modal-job-file').value=p})">Browse</button></div>
        </div>
        <button class="btn btn-success" onclick="doSubmitToWorkflow('${id}')">Submit</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doSubmitToWorkflow(id) {
    const file = document.getElementById('modal-job-file').value;
    closeModal();
    try {
        const result = await API.submitJob({wf_id: id, inputfile: file});
        Toast.success('Job submitted: ' + result.job_id.substr(0,8));
    } catch(e) { Toast.error('Error: ' + e.message); }
}

async function toggleWorkflow(id, state) {
    const action = state === 'stopped' || state === 'disabled' ? 'start' : 'stop';
    try { await API.setWorkflowState(id, action); Toast.info('Workflow ' + action + 'ed'); loadWorkflowList(); } catch(e) { Toast.error('Error: ' + e.message); }
}

async function deleteWorkflow(id) {
    showModal('Delete Workflow', `
        <p style="color:var(--text-secondary);margin-bottom:12px">Are you sure you want to delete this workflow?</p>
        <button class="btn btn-danger" onclick="doDeleteWorkflow('${id}')">Delete</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doDeleteWorkflow(id) {
    closeModal();
    try { await API.deleteWorkflow(id); Toast.success('Workflow deleted'); loadWorkflowList(); } catch(e) { Toast.error('Error: ' + e.message); }
}

async function loadWorkers() {
    try {
        const hosts = await API.getHosts();
        const now = Date.now() / 1000;
        let online = 0, offline = 0, capacity = 0;
        hosts.forEach(h => {
            if (h.active && (now - h.last_seen) < 60) { online++; capacity += h.max_jobs_per_class ? Object.values(h.max_jobs_per_class).reduce((a,b)=>a+b,0) : 8; }
            else { offline++; }
        });
        document.getElementById('worker-total').textContent = hosts.length;
        document.getElementById('worker-online').textContent = online;
        document.getElementById('worker-offline').textContent = offline;
        document.getElementById('worker-capacity').textContent = capacity;
        const grid = document.getElementById('workers-grid');
        if (hosts.length === 0) {
            grid.innerHTML = '<div class="panel" style="text-align:center;padding:40px;color:#555"><h3>No worker nodes</h3><p>Click "+ Add Worker" to register a worker node.</p></div>';
            return;
        }
        grid.innerHTML = hosts.map(h => {
            const isOnline = h.active && (now - h.last_seen) < 60;
            const jobs = h.current_jobs || 0;
            const maxJobs = h.max_jobs_per_class ? Object.values(h.max_jobs_per_class).reduce((a,b)=>a+b,0) : 8;
            const loadPct = maxJobs > 0 ? (jobs / maxJobs * 100) : 0;
            return `<div class="worker-card">
                <div class="worker-header">
                    <span class="worker-name">${h.name || h.hostname}</span>
                    <span class="worker-status ${isOnline?'online':'offline'}">${isOnline?'Online':'Offline'}</span>
                </div>
                <div class="worker-details">
                    <span>Host: ${h.hostname} | IP: ${h.ip}:${h.port}</span>
                    <span>Groups: ${(h.groups||[]).join(', ')||'default'}</span>
                    <span>Jobs: ${jobs}/${maxJobs} | CPU Roof: ${h.cpu_roof||20}%</span>
                    <span>Last seen: ${isOnline ? 'now' : Math.round(now - h.last_seen) + 's ago'}</span>
                </div>
                <div class="worker-bar"><div class="worker-bar-fill" style="width:${loadPct}%"></div></div>
            </div>`;
        }).join('');
    } catch(e) { console.error('Load workers error:', e); }
}

function showAddWorkerModal() {
    showModal('Add Worker Node', `
        <div class="form-group"><label>Worker Name</label><input type="text" id="worker-name" placeholder="worker-01"></div>
        <div class="form-group"><label>Hostname / IP</label><input type="text" id="worker-hostname" placeholder="192.168.1.100"></div>
        <div class="form-group"><label>API Port</label><input type="number" id="worker-port" value="8080"></div>
        <div class="form-group"><label>Groups (comma separated)</label><input type="text" id="worker-groups" value="default"></div>
        <div class="form-group"><label>Max Concurrent Jobs</label><input type="number" id="worker-max-jobs" value="4"></div>
        <button class="btn btn-primary" onclick="doAddWorker()">Register Worker</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doAddWorker() {
    const data = {
        name: document.getElementById('worker-name').value.trim(),
        hostname: document.getElementById('worker-hostname').value.trim(),
        port: parseInt(document.getElementById('worker-port').value) || 8080,
        groups: document.getElementById('worker-groups').value.split(',').map(s=>s.trim()).filter(Boolean),
        max_jobs: parseInt(document.getElementById('worker-max-jobs').value) || 4,
    };
    closeModal();
    try {
        await API.post('/hosts/register', data);
        Toast.success('Worker registered');
        loadWorkers();
    } catch(e) { Toast.error('Error: ' + e.message); }
}

function loadAllSettings() {
    fetch('/api/about').then(r => r.json()).then(d => {
        document.getElementById('set-hostname').value = d.hostname || '';
    }).catch(() => {});
    API.get('/settings').then(cfg => {
        if (cfg.port) document.getElementById('set-port').value = cfg.port;
        if (cfg.max_concurrent_jobs) document.getElementById('set-max-jobs').value = cfg.max_concurrent_jobs;
        if (cfg.input_dir) document.getElementById('set-input-dir').value = cfg.input_dir;
        if (cfg.output_dir) document.getElementById('set-output-dir').value = cfg.output_dir;
        if (cfg.ffmpeg_path) document.getElementById('set-ffmpeg').value = cfg.ffmpeg_path;
        if (cfg.ffprobe_path) document.getElementById('set-ffprobe').value = cfg.ffprobe_path;
    }).catch(() => {});
    API.getUserVars().then(vars => {
        const el = document.getElementById('user-vars-list');
        if (!vars || vars.length === 0) { el.innerHTML = '<p style="color:#555;font-size:.85em">No global variables defined.</p>'; return; }
        el.innerHTML = vars.map((v,i) => `<div class="var-row"><input value="${v.name}" placeholder="name" onchange="updateUserVar(${i},'name',this.value)"><input value="${v.value}" placeholder="value" onchange="updateUserVar(${i},'value',this.value)"><button class="btn btn-danger btn-xs" onclick="removeUserVar(${i})">X</button></div>`).join('');
    }).catch(() => {});
    API.getPresets().then(presets => {
        const el = document.getElementById('presets-list');
        const keys = Object.keys(presets || {});
        if (keys.length === 0) { el.innerHTML = '<p style="color:#555;font-size:.85em">No presets available.</p>'; return; }
        el.innerHTML = keys.map(k => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border);font-size:.85em"><span>${k}</span><button class="btn btn-xs btn-danger" onclick="deletePreset('${k}')">Delete</button></div>`).join('');
    }).catch(() => {});
}

function saveSettings() {
    const settings = {
        hostname: document.getElementById('set-hostname').value,
        port: document.getElementById('set-port').value,
        max_concurrent_jobs: document.getElementById('set-max-jobs').value,
        input_dir: document.getElementById('set-input-dir').value,
        output_dir: document.getElementById('set-output-dir').value,
        ffmpeg_path: document.getElementById('set-ffmpeg').value,
        ffprobe_path: document.getElementById('set-ffprobe').value,
    };
    API.post('/settings', settings).then(() => {
        Toast.success('Settings saved');
    }).catch(e => Toast.error('Error saving settings'));
}

function addUserVar() {
    showModal('Add Variable', `
        <div class="form-group"><label>Name</label><input type="text" id="var-name" placeholder="my_variable"></div>
        <div class="form-group"><label>Value</label><input type="text" id="var-value" placeholder="value"></div>
        <div class="form-group"><label>Type</label><select id="var-type"><option value="s">String</option><option value="i">Integer</option><option value="f">Float</option></select></div>
        <button class="btn btn-primary" onclick="doAddUserVar()">Add</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doAddUserVar() {
    const name = document.getElementById('var-name').value.trim();
    const value = document.getElementById('var-value').value;
    const vtype = document.getElementById('var-type').value;
    closeModal();
    try {
        await API.createUserVar({name, value, vtype});
        Toast.success('Variable added');
        loadAllSettings();
    } catch(e) { Toast.error('Error: ' + e.message); }
}

function importPresetModal() {
    showModal('Import Preset', `
        <div class="form-group"><label>Preset Name</label><input type="text" id="preset-name" placeholder="my_preset"></div>
        <div class="form-group"><label>Preset JSON</label><textarea id="preset-json" rows="8" style="font-family:monospace;font-size:.8em" placeholder='{"encoder":"libx264","crf":23}'></textarea></div>
        <button class="btn btn-primary" onclick="doImportPreset()">Import</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doImportPreset() {
    const name = document.getElementById('preset-name').value.trim();
    const json = document.getElementById('preset-json').value;
    closeModal();
    try {
        const data = JSON.parse(json);
        await API.post('/presets/import', {id: name, ...data});
        Toast.success('Preset imported');
        loadAllSettings();
    } catch(e) { Toast.error('Invalid JSON: ' + e.message); }
}

function showModal(title, html) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeModal();
    if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (editor && editor.workflowId) saveWorkflow();
    }
});
