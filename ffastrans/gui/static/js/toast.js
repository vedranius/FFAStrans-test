const Toast = {
    container: null,
    init() {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;';
        document.body.appendChild(this.container);
    },
    show(message, type = 'info', duration = 4000) {
        if (!this.container) this.init();
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = 'pointer-events:auto;min-width:300px;max-width:450px;padding:14px 20px;border-radius:8px;color:#fff;font-size:.9em;display:flex;align-items:center;gap:12px;box-shadow:0 8px 32px rgba(0,0,0,.4);animation:toastIn .3s ease;cursor:pointer;backdrop-filter:blur(10px);';
        const icons = {success:'&#10003;',error:'&#10007;',warning:'&#9888;',info:'&#8505;'};
        const colors = {success:'rgba(76,175,80,.95)',error:'rgba(244,67,54,.95)',warning:'rgba(255,152,0,.95)',info:'rgba(33,150,243,.95)'};
        toast.style.background = colors[type] || colors.info;
        toast.innerHTML = `<span style="font-size:1.3em">${icons[type]||icons.info}</span><span style="flex:1">${message}</span><span style="opacity:.6;font-size:.8em">✕</span>`;
        toast.addEventListener('click', () => { toast.style.animation = 'toastOut .3s ease forwards'; setTimeout(() => toast.remove(), 300); });
        this.container.appendChild(toast);
        if (duration > 0) setTimeout(() => { if (toast.parentNode) { toast.style.animation = 'toastOut .3s ease forwards'; setTimeout(() => toast.remove(), 300); } }, duration);
    },
    success(msg, dur) { this.show(msg, 'success', dur); },
    error(msg, dur) { this.show(msg, 'error', dur); },
    warning(msg, dur) { this.show(msg, 'warning', dur); },
    info(msg, dur) { this.show(msg, 'info', dur); },
};
