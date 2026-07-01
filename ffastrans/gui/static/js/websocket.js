class WSClient {
    constructor() {
        this.ws = null;
        this.listeners = {};
        this.reconnectDelay = 2000;
        this.connected = false;
    }
    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${proto}//${location.host}/ws/events`);
        this.ws.onopen = () => { this.connected = true; this.emit('connected'); };
        this.ws.onclose = () => { this.connected = false; this.emit('disconnected'); setTimeout(() => this.connect(), this.reconnectDelay); };
        this.ws.onerror = () => { this.connected = false; };
        this.ws.onmessage = (e) => {
            try {
                const msg = JSON.parse(e.data);
                this.emit(msg.type, msg.data);
                this.emit('message', msg);
            } catch(err) {}
        };
    }
    on(event, callback) {
        if (!this.listeners[event]) this.listeners[event] = [];
        this.listeners[event].push(callback);
        return () => { this.listeners[event] = this.listeners[event].filter(cb => cb !== callback); };
    }
    emit(event, data) {
        (this.listeners[event] || []).forEach(cb => cb(data));
    }
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(data));
    }
    disconnect() { if (this.ws) this.ws.close(); }
}
const ws = new WSClient();
