class FileBrowser {
    constructor(options = {}) {
        this.basePath = '';
        this.currentPath = '';
        this.selected = null;
        this.onSelect = options.onSelect || (() => {});
        this.onNavigate = options.onNavigate || (() => {});
        this.mode = options.mode || 'select';
        this.el = null;
    }
    async init() {
        try {
            const resp = await fetch('/api/files/browse');
            const data = await resp.json();
            this.basePath = data.path || '/tmp';
            this.currentPath = this.basePath;
        } catch(e) { this.basePath = '/tmp'; this.currentPath = '/tmp'; }
    }
    async render(container) {
        this.el = container;
        await this.init();
        this.loadDir(this.currentPath);
    }
    async load(path) {
        this.currentPath = path;
        try {
            const url = `/api/files/browse?path=${encodeURIComponent(path)}`;
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(resp.statusText);
            const data = await resp.json();
            this.currentPath = data.path || path;
            this.renderDir(data);
        } catch(e) { Toast.error('Cannot browse: ' + e.message); }
    }
    loadDir(path) {
        this.load(path);
    }
    renderDir(data) {
        if (!this.el) return;
        const items = data.items || [];
        const displayPath = this.currentPath.replace(this.basePath, '~');
        const pathParts = this.currentPath.split('/').filter(Boolean);
        let html = `<div class="fb-breadcrumb"><span class="fb-crumb" onclick="fileBrowser.loadDir(fileBrowser.basePath)">${this.basePath.split('/').pop() || '/'}</span>`;
        let accumulated = '';
        pathParts.forEach(part => {
            accumulated += '/' + part;
            const p = accumulated;
            html += `<span class="fb-sep">/</span><span class="fb-crumb" onclick="fileBrowser.load('${p}')">${part}</span>`;
        });
        html += '</div>';
        if (this.mode === 'upload') {
            html += `<div class="fb-upload-zone" id="fb-drop-zone"><div class="fb-upload-icon">&#8686;</div><div>Drag files here or <label class="fb-upload-label">browse<input type="file" multiple id="fb-file-input" style="display:none" onchange="fileBrowser.handleUpload(this.files)"></label></div></div>`;
        }
        html += '<div class="fb-list">';
        if (this.currentPath !== this.basePath) {
            const parent = this.currentPath.split('/').slice(0, -1).join('/') || this.basePath;
            html += `<div class="fb-item fb-folder" onclick="fileBrowser.load('${parent}')"><span class="fb-icon">&#128193;</span><span class="fb-name">..</span><span class="fb-type">Parent</span></div>`;
        }
        items.forEach(item => {
            const icon = item.is_dir ? '&#128193;' : '&#128196;';
            const cls = item.is_dir ? 'fb-folder' : 'fb-file';
            const click = item.is_dir ? `fileBrowser.load('${item.path.replace(/'/g, "\\'")}')` : `fileBrowser.selectFile('${item.path.replace(/'/g, "\\'")}')`;
            const size = item.is_dir ? '-' : this.formatSize(item.size);
            html += `<div class="fb-item ${cls}" onclick="${click}"><span class="fb-icon">${icon}</span><span class="fb-name">${item.name}</span><span class="fb-size">${size}</span></div>`;
        });
        if (items.length === 0) html += '<div class="fb-empty">Empty directory</div>';
        html += '</div>';
        if (this.mode === 'select' || this.mode === 'output') {
            html += `<div class="fb-actions"><input type="text" id="fb-selected-path" class="fb-path-input" value="${this.currentPath}" placeholder="Selected path"><button class="btn btn-primary" onclick="fileBrowser.confirmSelection()">Select</button></div>`;
        }
        this.el.innerHTML = html;
        this.setupDragDrop();
        this.onNavigate(this.currentPath);
    }
    selectFile(path) {
        this.selected = path;
        const input = document.getElementById('fb-selected-path');
        if (input) input.value = path;
        document.querySelectorAll('.fb-item').forEach(el => el.classList.remove('fb-selected'));
        if (event && event.currentTarget) event.currentTarget.classList.add('fb-selected');
    }
    confirmSelection() {
        const input = document.getElementById('fb-selected-path');
        const path = input ? input.value : this.selected || this.currentPath;
        this.onSelect(path);
    }
    formatSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B','KB','MB','GB','TB'];
        let i = 0, size = bytes;
        while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
        return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    }
    setupDragDrop() {
        const zone = document.getElementById('fb-drop-zone');
        if (!zone) return;
        ['dragenter','dragover'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('fb-drop-active'); }));
        ['dragleave','drop'].forEach(ev => zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('fb-drop-active'); }));
        zone.addEventListener('drop', e => { if (e.dataTransfer.files.length) this.handleUpload(e.dataTransfer.files); });
    }
    async handleUpload(files) {
        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('path', this.currentPath);
            try {
                Toast.info(`Uploading ${file.name}...`);
                const resp = await fetch('/api/files/upload', { method: 'POST', body: formData });
                if (!resp.ok) {
                    const err = await resp.json().catch(() => ({}));
                    throw new Error(err.detail || resp.statusText);
                }
                const result = await resp.json();
                Toast.success(`${file.name} uploaded (${this.formatSize(result.size)})`);
                if (this.onSelect && this.mode === 'upload') {
                    this.onSelect(result.path);
                }
            } catch(e) { Toast.error(`Upload failed: ${e.message}`); }
        }
        this.load(this.currentPath);
    }
    static open(options = {}) {
        const overlay = document.createElement('div');
        overlay.className = 'fb-overlay';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:500;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px)';
        const modal = document.createElement('div');
        modal.className = 'fb-modal';
        modal.style.cssText = 'background:var(--bg-secondary);border:1px solid var(--border);border-radius:10px;width:90%;max-width:700px;max-height:80vh;display:flex;flex-direction:column;overflow:hidden';
        const header = document.createElement('div');
        header.style.cssText = 'padding:14px 18px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center';
        header.innerHTML = `<h3 style="margin:0;font-size:1em">${options.title || 'Browse Files'}</h3><button class="modal-close" onclick="this.closest('.fb-overlay').remove()" style="background:none;border:none;color:var(--text-secondary);font-size:1.4em;cursor:pointer">&times;</button>`;
        const body = document.createElement('div');
        body.style.cssText = 'flex:1;overflow-y:auto;padding:14px';
        modal.appendChild(header);
        modal.appendChild(body);
        overlay.appendChild(modal);
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
        document.body.appendChild(overlay);
        const browser = new FileBrowser({
            path: options.path,
            mode: options.mode || 'select',
            onSelect: (path) => { overlay.remove(); if (options.onSelect) options.onSelect(path); },
        });
        window.fileBrowser = browser;
        browser.render(body);
        return overlay;
    }
}
