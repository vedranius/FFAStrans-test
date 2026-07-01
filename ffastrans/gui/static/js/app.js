let editor = null;
let currentSection = 'dashboard';

document.addEventListener('DOMContentLoaded', () => {
    showSection('dashboard');
    loadDashboard();
    initWorkflowEditor();
    loadNodePalette();
    setInterval(loadDashboard, 5000);
    loadSettings();
});

function showSection(id) {
    currentSection = id;
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
    document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
    const links = document.querySelectorAll('nav a');
    links.forEach(a => {
        if ((id === 'dashboard' && a.textContent === 'Dashboard') ||
            (id === 'workflows' && a.textContent === 'Workflows') ||
            (id === 'settings' && a.textContent === 'Settings')) {
            a.classList.add('active');
        }
    });
    if (id === 'dashboard') loadDashboard();
    if (id === 'workflows') loadWorkflowList();
}

function loadSettings() {
    fetch('/api/about').then(r => r.json()).then(d => {
        document.getElementById('set-hostname').value = d.hostname || '';
    }).catch(() => {});
}

async function loadDashboard() {
    try {
        const [jobs, wfs, hist] = await Promise.all([
            API.getActiveJobs().catch(() => []),
            API.getWorkflows().catch(() => []),
            API.getHistory(0, 50).catch(() => [])
        ]);
        document.getElementById('active-jobs-count').textContent = jobs.length;
        document.getElementById('workflow-count').textContent = wfs.length;
        document.getElementById('completed-count').textContent = hist.filter(h => h.state === 'completed').length;
        document.getElementById('failed-count').textContent = hist.filter(h => h.state === 'failed').length;

        const tbody = document.querySelector('#active-jobs-table tbody');
        if (jobs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:#666">No active jobs</td></tr>';
        } else {
            tbody.innerHTML = jobs.map(j => `<tr>
                <td>${j.id.substr(0,8)}</td><td>${j.wf_id}</td>
                <td>${(j.input_file||'').split('/').pop()}</td>
                <td><span class="state-badge state-${j.state}">${j.state}</span></td>
                <td>${Math.round(j.total_progress)}%</td>
                <td><button class="btn btn-danger btn-sm" onclick="abortJob('${j.id}')">Abort</button></td>
            </tr>`).join('');
        }

        const htbody = document.querySelector('#history-table tbody');
        if (hist.length === 0) {
            htbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#666">No history yet</td></tr>';
        } else {
            htbody.innerHTML = hist.slice(0, 20).map(h => {
                const dur = h.finished_at && h.started_at ? Math.round(h.finished_at - h.started_at) + 's' : '-';
                return `<tr><td>${new Date(h.started_at*1000).toLocaleTimeString()}</td>
                    <td>${h.wf_name||h.wf_id}</td><td>${(h.input_file||'').split('/').pop()}</td>
                    <td><span class="state-badge state-${h.state}">${h.state}</span></td><td>${dur}</td></tr>`;
            }).join('');
        }
    } catch(e) { console.error('Dashboard error:', e); }
}

async function abortJob(id) {
    if (!confirm('Abort this job?')) return;
    try { await API.jobAction(id, 'abort'); loadDashboard(); } catch(e) { alert('Error: ' + e.message); }
}

function loadNodePalette() {
    API.getNodes().then(categories => {
        const palette = document.getElementById('node-palette');
        let html = '<h3 style="font-size:.9em;margin-bottom:10px;color:#aaa">Drag nodes to canvas</h3>';
        for (const [cat, nodes] of Object.entries(categories)) {
            html += `<div class="palette-category"><h4>${cat}</h4>`;
            for (const n of nodes) {
                html += `<div class="palette-item" draggable="true" data-type="${n.type}" data-name="${n.name}" title="${n.type}">${n.name}</div>`;
            }
            html += '</div>';
        }
        palette.innerHTML = html;
        palette.querySelectorAll('.palette-item').forEach(item => {
            item.addEventListener('dragstart', e => {
                e.dataTransfer.setData('text/plain', item.dataset.type);
                e.dataTransfer.setData('application/name', item.dataset.name);
            });
        });
    });
}

async function loadWorkflowList() {
    try {
        const wfs = await API.getWorkflows();
        const list = document.getElementById('workflow-list');
        if (wfs.length === 0) {
            list.innerHTML = '<div class="panel" style="text-align:center;padding:40px;color:#666"><h3>No workflows yet</h3><p>Click "+ New Workflow" to create your first workflow.</p></div>';
            return;
        }
        list.innerHTML = wfs.map(wf => `
            <div class="workflow-card" onclick="openWorkflow('${wf.id}')">
                <div class="wf-info">
                    <h3>${wf.name}</h3>
                    <p>ID: ${wf.id} | Nodes: ${(wf.nodes||[]).length} | State: <span class="state-badge state-${wf.state}">${wf.state}</span></p>
                </div>
                <div class="wf-actions">
                    <button class="btn btn-sm" onclick="event.stopPropagation();toggleWorkflow('${wf.id}','${wf.state}')">${wf.state==='stopped'||wf.state==='disabled'?'Start':'Stop'}</button>
                    <button class="btn btn-sm" onclick="event.stopPropagation();submitToWorkflow('${wf.id}')">Run</button>
                    <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteWorkflow('${wf.id}')">Delete</button>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error('Load workflows error:', e); document.getElementById('workflow-list').innerHTML = '<p style="color:red">Error loading workflows</p>'; }
}

function createNewWorkflow() {
    showModal('New Workflow', `
        <div class="form-group"><label>Workflow Name</label><input type="text" id="modal-wf-name" value="New Workflow"></div>
        <button class="btn btn-primary" onclick="doCreateWorkflow()">Create</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
    setTimeout(() => document.getElementById('modal-wf-name').focus(), 100);
}

async function doCreateWorkflow() {
    const name = document.getElementById('modal-wf-name').value.trim();
    if (!name) return;
    closeModal();
    try {
        const wf = await API.createWorkflow({name, nodes:[], connections:[], variables:[]});
        openWorkflow(wf.id);
    } catch(e) { alert('Error: ' + e.message); }
}

async function importWorkflow() {
    showModal('Import Workflow', `
        <div class="form-group"><label>Paste workflow JSON</label><textarea id="modal-wf-json" rows="10" style="width:100%;font-family:monospace;font-size:.8em"></textarea></div>
        <button class="btn btn-primary" onclick="doImportWorkflow()">Import</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doImportWorkflow() {
    const json = document.getElementById('modal-wf-json').value;
    if (!json.trim()) return;
    try {
        const data = JSON.parse(json);
        await API.post('/workflows/import', data);
        closeModal();
        loadWorkflowList();
    } catch(e) { alert('Invalid JSON: ' + e.message); }
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

        setTimeout(() => {
            const container = document.getElementById('canvas-container');
            const canvas = document.getElementById('wf-canvas');
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight || 600;
            editor.draw();
        }, 50);
    } catch(e) { alert('Error: ' + e.message); }
}

function closeEditor() {
    document.getElementById('wf-editor').style.display = 'none';
    document.getElementById('workflow-list').style.display = 'block';
    document.querySelector('#workflows .toolbar').style.display = 'flex';
    loadWorkflowList();
}

async function saveWorkflow() {
    if (!editor || !editor.workflowId) return;
    try {
        const data = editor.toJSON();
        await API.updateWorkflow(editor.workflowId, data);
        alert('Saved!');
    } catch(e) { alert('Error: ' + e.message); }
}

async function runWorkflow() {
    if (!editor || !editor.workflowId) return;
    showModal('Submit Job', `
        <div class="form-group"><label>Input File Path</label><input type="text" id="modal-job-file" value="" placeholder="/path/to/file.mp4"></div>
        <p style="color:#666;font-size:.85em">Leave empty if workflow uses a monitor node.</p>
        <button class="btn btn-success" onclick="doRunWorkflow()">Submit</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doRunWorkflow() {
    const file = document.getElementById('modal-job-file').value;
    closeModal();
    try {
        const result = await API.submitJob({wf_id: editor.workflowId, inputfile: file});
        alert('Job submitted: ' + result.job_id);
    } catch(e) { alert('Error: ' + e.message); }
}

async function toggleWorkflow(id, state) {
    const action = state === 'stopped' || state === 'disabled' ? 'start' : 'stop';
    try { await API.setWorkflowState(id, action); loadWorkflowList(); } catch(e) { alert('Error: ' + e.message); }
}

async function submitToWorkflow(id) {
    showModal('Submit Job', `
        <div class="form-group"><label>Input File Path</label><input type="text" id="modal-job-file" value="" placeholder="/path/to/file.mp4"></div>
        <button class="btn btn-success" onclick="doSubmitToWorkflow('${id}')">Submit</button>
        <button class="btn" onclick="closeModal()">Cancel</button>
    `);
}

async function doSubmitToWorkflow(id) {
    const file = document.getElementById('modal-job-file').value;
    closeModal();
    try {
        const result = await API.submitJob({wf_id: id, inputfile: file});
        alert('Job submitted: ' + result.job_id);
    } catch(e) { alert('Error: ' + e.message); }
}

async function deleteWorkflow(id) {
    if (!confirm('Delete this workflow?')) return;
    try { await API.deleteWorkflow(id); loadWorkflowList(); } catch(e) { alert('Error: ' + e.message); }
}

function showModal(title, html) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('modal').style.display = 'none';
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
