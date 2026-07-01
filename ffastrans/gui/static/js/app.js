let editor = null;

document.addEventListener('DOMContentLoaded', async () => {
    editor = new WorkflowEditor('wf-canvas');
    showSection('dashboard');
    setupNavigation();
    loadDashboard();
    loadNodePalette();
    setupWorkflowUI();
    setInterval(refreshDashboard, 5000);
});

function showSection(id) {
    document.querySelectorAll('.section').forEach(s => s.style.display = 'none');
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
    document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));
    const link = document.querySelector(`nav a[href="/#${id}"], nav a[href="/"]`);
    if (link) link.classList.add('active');
}

function setupNavigation() {
    document.querySelectorAll('nav a').forEach(a => {
        a.addEventListener('click', e => {
            e.preventDefault();
            const href = a.getAttribute('href');
            if (href === '/') showSection('dashboard');
            else if (href === '/monitor') window.location.href = '/monitor';
            else showSection(href.replace('#', ''));
        });
    });
}

async function loadDashboard() {
    try {
        const [jobs, wfs, hist] = await Promise.all([API.getActiveJobs(), API.getWorkflows(), API.getHistory(0, 50)]);
        document.getElementById('active-jobs-count').textContent = jobs.length;
        document.getElementById('workflow-count').textContent = wfs.length;
        document.getElementById('completed-count').textContent = hist.filter(h => h.state === 'completed').length;
        document.getElementById('failed-count').textContent = hist.filter(h => h.state === 'failed').length;

        const tbody = document.querySelector('#active-jobs-table tbody');
        tbody.innerHTML = jobs.length === 0 ? '<tr><td colspan="6" style="text-align:center;color:#aaa">No active jobs</td></tr>' :
            jobs.map(j => `<tr>
                <td>${j.id.substr(0,8)}</td><td>${j.wf_id}</td><td>${j.input_file.split('/').pop()}</td>
                <td class="state-${j.state}">${j.state}</td>
                <td>${Math.round(j.total_progress)}%</td>
                <td><button class="btn btn-danger btn-sm" onclick="abortJob('${j.id}')">Abort</button></td>
            </tr>`).join('');

        const htbody = document.querySelector('#history-table tbody');
        htbody.innerHTML = hist.slice(0, 20).map(h => {
            const dur = h.finished_at && h.started_at ? Math.round(h.finished_at - h.started_at) + 's' : '-';
            return `<tr><td>${new Date(h.started_at*1000).toLocaleTimeString()}</td><td>${h.wf_name||h.wf_id}</td>
                <td>${(h.input_file||'').split('/').pop()}</td><td class="state-${h.state}">${h.state}</td><td>${dur}</td></tr>`;
        }).join('');
    } catch(e) { console.error('Dashboard error:', e); }
}

function refreshDashboard() { loadDashboard(); }

async function abortJob(id) {
    if (!confirm('Abort this job?')) return;
    try { await API.jobAction(id, 'abort'); loadDashboard(); } catch(e) { alert('Error: ' + e.message); }
}

function loadNodePalette() {
    API.getNodes().then(categories => {
        const palette = document.getElementById('node-palette');
        let html = '<h3 style="font-size:.9em;margin-bottom:10px;color:#aaa">Node Palette</h3>';
        for (const [cat, nodes] of Object.entries(categories)) {
            html += `<div class="palette-category"><h4>${cat}</h4>`;
            for (const n of nodes) {
                html += `<div class="palette-item" draggable="true" data-type="${n.type}" data-name="${n.name}">${n.name}</div>`;
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

function setupWorkflowUI() {
    const canvas = document.getElementById('wf-canvas');
    canvas.addEventListener('dragover', e => e.preventDefault());
    canvas.addEventListener('drop', e => {
        e.preventDefault();
        const type = e.dataTransfer.getData('text/plain');
        const name = e.dataTransfer.getData('application/name');
        const rect = canvas.getBoundingClientRect();
        editor.addNode(type, e.clientX - rect.left, e.clientY - rect.top, name);
    });

    document.getElementById('btn-new-wf').addEventListener('click', createNewWorkflow);
    document.getElementById('btn-import-wf').addEventListener('click', importWorkflow);
    document.getElementById('btn-save-wf').addEventListener('click', saveWorkflow);
    document.getElementById('btn-run-wf').addEventListener('click', runWorkflow);
    document.getElementById('btn-back-wf').addEventListener('click', () => {
        document.getElementById('wf-editor').style.display = 'none';
        document.querySelector('.workflow-list').style.display = 'block';
        loadWorkflowList();
    });

    loadWorkflowList();
}

async function loadWorkflowList() {
    try {
        const wfs = await API.getWorkflows();
        const list = document.getElementById('workflow-list');
        if (wfs.length === 0) {
            list.innerHTML = '<p style="color:#aaa;text-align:center;padding:20px">No workflows. Click "+ New Workflow" to create one.</p>';
            return;
        }
        list.innerHTML = wfs.map(wf => `
            <div class="workflow-card" onclick="openWorkflow('${wf.id}')">
                <div class="wf-info">
                    <h3>${wf.name}</h3>
                    <p>ID: ${wf.id} | Nodes: ${(wf.nodes||[]).length} | State: <span class="state-badge state-${wf.state}">${wf.state}</span></p>
                </div>
                <div class="wf-actions">
                    <button class="btn btn-sm" onclick="event.stopPropagation();toggleWorkflow('${wf.id}','${wf.state}')">
                        ${wf.state === 'stopped' || wf.state === 'disabled' ? 'Start' : 'Stop'}
                    </button>
                    <button class="btn btn-sm" onclick="event.stopPropagation();submitToWorkflow('${wf.id}')">Submit Job</button>
                    <button class="btn btn-danger btn-sm" onclick="event.stopPropagation();deleteWorkflow('${wf.id}')">Delete</button>
                </div>
            </div>
        `).join('');
    } catch(e) { console.error('Load workflows error:', e); }
}

async function createNewWorkflow() {
    const name = prompt('Workflow name:', 'New Workflow');
    if (!name) return;
    try {
        const wf = await API.createWorkflow({name, nodes:[], connections:[], variables:[]});
        openWorkflow(wf.id);
    } catch(e) { alert('Error: ' + e.message); }
}

async function importWorkflow() {
    const json = prompt('Paste exported workflow JSON:');
    if (!json) return;
    try {
        const data = JSON.parse(json);
        await API.post('/workflows/import', data);
        loadWorkflowList();
    } catch(e) { alert('Error: ' + e.message); }
}

async function openWorkflow(id) {
    try {
        const wf = await API.getWorkflow(id);
        editor.loadWorkflow(wf);
        document.getElementById('wf-editor').style.display = 'flex';
        document.querySelector('.workflow-list').style.display = 'none';
        setTimeout(() => editor.resize(), 100);
    } catch(e) { alert('Error loading workflow: ' + e.message); }
}

async function saveWorkflow() {
    if (!editor.workflowId) return;
    try {
        const data = editor.toJSON();
        await API.updateWorkflow(editor.workflowId, data);
        alert('Workflow saved!');
    } catch(e) { alert('Error saving: ' + e.message); }
}

async function runWorkflow() {
    if (!editor.workflowId) return;
    const file = prompt('Input file path (or leave empty for monitor):', '');
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
    const file = prompt('Input file path:', '');
    if (file === null) return;
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

window.addEventListener('resize', () => { if (editor) editor.resize(); });
