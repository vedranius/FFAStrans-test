class WorkflowEditor {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.nodes = [];
        this.connections = [];
        this.selectedNode = null;
        this.dragging = null;
        this.connecting = null;
        this.offset = {x:0, y:0};
        this.workflowId = null;
        this.workflowName = '';
        this.variables = [];
        this.initEvents();
    }

    initEvents() {
        this.canvas.addEventListener('mousedown', e => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', e => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', e => this.onMouseUp(e));
        this.canvas.addEventListener('contextmenu', e => { e.preventDefault(); });
        this.canvas.addEventListener('dblclick', e => this.onDblClick(e));
        window.addEventListener('resize', () => this.resize());
        const ro = new ResizeObserver(() => this.resize());
        ro.observe(this.canvas.parentElement);
    }

    resize() {
        const container = this.canvas.parentElement;
        if (container && container.clientWidth > 0) {
            this.canvas.width = container.clientWidth;
            this.canvas.height = Math.max(container.clientHeight, 500);
            this.draw();
        }
    }

    loadWorkflow(wf) {
        this.workflowId = wf.id;
        this.workflowName = wf.name;
        this.nodes = (wf.nodes || []).map(n => typeof n === 'string' ? JSON.parse(n) : n);
        this.connections = (wf.connections || []).map(c => typeof c === 'string' ? JSON.parse(c) : c);
        this.variables = wf.variables || [];
        this.draw();
    }

    addNode(type, x, y, name) {
        const id = 'n' + Date.now().toString(36);
        const node = {id, name: name || type, node_type: type, x, y, params:{}, state:'idle', preset_id:null};
        this.nodes.push(node);
        this.selectNode(node);
        this.draw();
        return node;
    }

    removeNode(id) {
        this.nodes = this.nodes.filter(n => n.id !== id);
        this.connections = this.connections.filter(c => c.from_node !== id && c.to_node !== id);
        if (this.selectedNode && this.selectedNode.id === id) this.selectedNode = null;
        this.draw();
        this.showProperties(null);
    }

    selectNode(node) {
        this.selectedNode = node;
        this.showProperties(node);
        this.draw();
    }

    getNodeAt(x, y) {
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const n = this.nodes[i];
            if (x >= n.x && x <= n.x + 140 && y >= n.y && y <= n.y + 50) return n;
        }
        return null;
    }

    getPortPos(node, port) {
        if (port === 'output' || port === 'error') {
            return {x: node.x + 140, y: node.y + 25};
        }
        return {x: node.x, y: node.y + 25};
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (e.button === 2) {
            const node = this.getNodeAt(x, y);
            if (node) this.selectNode(node);
            return;
        }

        const node = this.getNodeAt(x, y);
        if (node) {
            this.dragging = node;
            this.offset = {x: x - node.x, y: y - node.y};
            this.selectNode(node);
        } else {
            this.selectNode(null);
        }
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        if (this.dragging) {
            this.dragging.x = x - this.offset.x;
            this.dragging.y = y - this.offset.y;
            this.draw();
        }
    }

    onMouseUp(e) {
        if (this.dragging) {
            this.dragging = null;
        }
    }

    onDblClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const node = this.getNodeAt(x, y);
        if (node) {
            this.selectNode(node);
        }
    }

    draw() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        ctx.strokeStyle = '#0f3460';
        ctx.lineWidth = 2;
        this.connections.forEach(c => {
            const from = this.nodes.find(n => n.id === c.from_node);
            const to = this.nodes.find(n => n.id === c.to_node);
            if (from && to) {
                const p1 = this.getPortPos(from, c.from_port || 'output');
                const p2 = this.getPortPos(to, c.to_port || 'input');
                ctx.beginPath();
                ctx.moveTo(p1.x, p1.y);
                const cp = (p2.x - p1.x) * 0.5;
                ctx.bezierCurveTo(p1.x + cp, p1.y, p2.x - cp, p2.y, p2.x, p2.y);
                ctx.stroke();
            }
        });

        this.nodes.forEach(n => {
            const selected = this.selectedNode && this.selectedNode.id === n.id;
            const stateColors = {idle:'#334',running:'#0f3460',completed:'#1b5e20',failed:'#b71c1c',skipped:'#555'};
            ctx.fillStyle = stateColors[n.state] || '#1a1a2e';
            ctx.strokeStyle = selected ? '#e94560' : '#444';
            ctx.lineWidth = selected ? 2 : 1;
            ctx.fillRect(n.x, n.y, 140, 50);
            ctx.strokeRect(n.x, n.y, 140, 50);

            ctx.fillStyle = '#fff';
            ctx.font = '11px sans-serif';
            ctx.fillText(n.name || n.node_type, n.x + 5, n.y + 20);
            ctx.fillStyle = '#aaa';
            ctx.font = '9px sans-serif';
            ctx.fillText(n.node_type, n.x + 5, n.y + 38);

            ctx.fillStyle = '#e94560';
            ctx.beginPath();
            ctx.arc(n.x, n.y + 25, 5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#4caf50';
            ctx.beginPath();
            ctx.arc(n.x + 140, n.y + 25, 5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#f44336';
            ctx.beginPath();
            ctx.arc(n.x + 140, n.y + 40, 4, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    showProperties(node) {
        const panel = document.getElementById('properties-panel');
        if (!node) {
            panel.innerHTML = '<h3>Properties</h3><p style="color:#aaa;font-size:.85em">Select a node to edit its properties.</p>';
            return;
        }

        const paramFields = this.getParamFields(node.node_type);
        let html = `<h3>${node.name || node.node_type}</h3>`;
        html += `<div class="prop-group"><label>Name</label><input id="prop-name" value="${node.name||''}" onchange="editor.updateNodeProp('name',this.value)"></div>`;

        paramFields.forEach(f => {
            const val = node.params[f.key] || f.default || '';
            if (f.type === 'select') {
                const opts = f.options.map(o => `<option value="${o}" ${val===o?'selected':''}>${o}</option>`).join('');
                html += `<div class="prop-group"><label>${f.label}</label><select id="prop-${f.key}" onchange="editor.updateNodeParam('${f.key}',this.value)">${opts}</select></div>`;
            } else if (f.type === 'textarea') {
                html += `<div class="prop-group"><label>${f.label}</label><textarea id="prop-${f.key}" rows="3" onchange="editor.updateNodeParam('${f.key}',this.value)">${val}</textarea></div>`;
            } else {
                html += `<div class="prop-group"><label>${f.label}</label><input id="prop-${f.key}" value="${val}" onchange="editor.updateNodeParam('${f.key}',this.value)"></div>`;
            }
        });

        html += `<div style="margin-top:15px"><button class="btn btn-danger btn-sm" onclick="editor.removeNode('${node.id}')">Delete Node</button></div>`;
        panel.innerHTML = html;
    }

    updateNodeProp(key, val) {
        if (this.selectedNode) { this.selectedNode[key] = val; this.draw(); }
    }

    updateNodeParam(key, val) {
        if (this.selectedNode) { this.selectedNode.params = this.selectedNode.params || {}; this.selectedNode.params[key] = val; }
    }

    addConnection(fromId, toId, fromPort, toPort) {
        this.connections.push({from_node:fromId, to_node:toId, from_port:fromPort||'output', to_port:toPort||'input'});
        this.draw();
    }

    removeConnection(idx) {
        this.connections.splice(idx, 1);
        this.draw();
    }

    getParamFields(nodeType) {
        const fields = {
            mon_folder: [
                {key:'path',label:'Watch Path',type:'text',default:'drop_folders/input'},
                {key:'filter',label:'File Filter',type:'text',default:'*.*'},
                {key:'mode',label:'Mode',type:'select',options:['new','once'],default:'new'},
                {key:'recursive',label:'Recursive',type:'select',options:['true','false'],default:'false'},
                {key:'poll_interval',label:'Poll Interval (s)',type:'text',default:'2'},
            ],
            mon_sequence: [
                {key:'path',label:'Sequence Path',type:'text'},
                {key:'pattern',label:'Pattern',type:'text',default:'%04d'},
                {key:'start',label:'Start Frame',type:'text',default:'0'},
                {key:'end',label:'End Frame',type:'text',default:'100'},
                {key:'extension',label:'Extension',type:'text',default:'dpx'},
            ],
            enc_av_mp4: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'vcodec',label:'Video Codec',type:'select',options:['libx264','libx265','copy'],default:'libx264'},
                {key:'video_bitrate',label:'Video Bitrate',type:'text',default:'5M'},
                {key:'crf',label:'CRF',type:'text',default:'23'},
                {key:'preset',label:'Preset',type:'select',options:['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'],default:'medium'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv420p','yuv422p','yuv444p','yuv420p10le'],default:'yuv420p'},
                {key:'profile',label:'Profile',type:'select',options:['baseline','main','high','high10'],default:'high'},
                {key:'acodec',label:'Audio Codec',type:'select',options:['aac','mp3','copy','none'],default:'aac'},
                {key:'audio_bitrate',label:'Audio Bitrate',type:'text',default:'192k'},
            ],
            enc_av_265: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'crf',label:'CRF',type:'text',default:'28'},
                {key:'preset',label:'Preset',type:'select',options:['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'],default:'medium'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv420p','yuv420p10le','yuv422p10le'],default:'yuv420p'},
                {key:'hdr',label:'HDR',type:'select',options:['true','false'],default:'false'},
            ],
            enc_av_prores: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'profile',label:'Profile (0-3)',type:'select',options:['0','1','2','3'],default:'3'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv422p','yuv422p10le','yuv444p','yuv444p10le'],default:'yuv422p10le'},
            ],
            enc_av_dnxhr: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'dnxhr_profile',label:'Profile',type:'select',options:['DNxHR LB','DNxHR SQ','DNxHR HQ','DNxHR HQX','DNxHR 444'],default:'DNxHR HQ'},
            ],
            enc_av_customff: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'ffmpeg_args',label:'FFmpeg Args',type:'textarea'},
            ],
            enc_a_audio: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'acodec',label:'Audio Codec',type:'select',options:['pcm_s16le','pcm_s24le','pcm_s32le','aac','mp3','flac'],default:'pcm_s16le'},
                {key:'audio_sample_rate',label:'Sample Rate',type:'select',options:['44100','48000','96000'],default:'48000'},
                {key:'audio_channels',label:'Channels',type:'select',options:['1','2','6','8'],default:'2'},
            ],
            dec_avmedia: [
                {key:'input',label:'Input File',type:'text'},
            ],
            dec_stills: [
                {key:'input',label:'Input File',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'framerate',label:'Frame Rate',type:'text',default:'25'},
                {key:'duration',label:'Duration (s)',type:'text',default:'5'},
                {key:'resolution',label:'Resolution',type:'select',options:['1920x1080','3840x2160','1280x720'],default:'1920x1080'},
            ],
            avs_v_resize: [{key:'width',label:'Width',type:'text',default:'1920'},{key:'height',label:'Height',type:'text',default:'1080'},{key:'interpolation',label:'Algorithm',type:'select',options:['lanczos','bilinear','bicubic'],default:'lanczos'}],
            avs_v_crop: [{key:'x',label:'X',type:'text',default:'0'},{key:'y',label:'Y',type:'text',default:'0'},{key:'width',label:'Width',type:'text',default:'1920'},{key:'height',label:'Height',type:'text',default:'1080'}],
            avs_v_color: [{key:'brightness',label:'Brightness',type:'text',default:'0'},{key:'contrast',label:'Contrast',type:'text',default:'1'},{key:'saturation',label:'Saturation',type:'text',default:'1'},{key:'gamma',label:'Gamma',type:'text',default:'1'}],
            avs_v_watermark: [{key:'watermark_path',label:'Watermark Image',type:'text'},{key:'position',label:'Position',type:'select',options:['top_left','top_right','bottom_left','bottom_right','center'],default:'top_right'}],
            avs_v_tc: [{key:'text',label:'Text',type:'text',default:'%%s_datetime%%'},{key:'position',label:'Position',type:'select',options:['top_left','top_right','bottom_left','bottom_right'],default:'bottom_right'},{key:'fontsize',label:'Font Size',type:'text',default:'24'}],
            avs_v_deinterlace: [{key:'mode',label:'Mode',type:'select',options:['bob','weave'],default:'bob'}],
            avs_v_pad: [{key:'width',label:'Width',type:'text',default:'1920'},{key:'height',label:'Height',type:'text',default:'1080'},{key:'color',label:'Color',type:'select',options:['black','white'],default:'black'}],
            avs_v_flip: [{key:'direction',label:'Direction',type:'select',options:['horizontal','vertical'],default:'horizontal'}],
            avs_v_fpsconv: [{key:'target_fps',label:'Target FPS',type:'text',default:'25'},{key:'algorithm',label:'Algorithm',type:'select',options:['mci','blend'],default:'mci'}],
            op_cond: [{key:'variable',label:'Variable',type:'text'},{key:'condition',label:'Condition',type:'select',options:['equals','not_equals','contains','gt','lt','exists'],default:'equals'},{key:'value',label:'Compare Value',type:'text'}],
            op_populate: [{key:'template',label:'Template Text',type:'textarea'},{key:'output_path',label:'Output Path',type:'text'}],
            op_analyzer: [{key:'input',label:'Input File',type:'text'}],
            op_foreach: [{key:'variable',label:'Variable Name',type:'text',default:'s_item'},{key:'items',label:'Items (comma sep)',type:'text'}],
            op_hold: [{key:'seconds',label:'Seconds',type:'text',default:'5'}],
            cmd_run: [{key:'command',label:'Command',type:'textarea'}],
            other_email: [{key:'smtp_server',label:'SMTP Server',type:'text'},{key:'smtp_port',label:'Port',type:'text',default:'587'},{key:'from',label:'From',type:'text'},{key:'to',label:'To',type:'text'},{key:'subject',label:'Subject',type:'text'},{key:'body',label:'Body',type:'textarea'}],
            other_httpsend: [{key:'url',label:'URL',type:'text'},{key:'method',label:'Method',type:'select',options:['GET','POST','PUT','DELETE'],default:'GET'},{key:'body',label:'Body (JSON)',type:'textarea'}],
            other_textfile: [{key:'content',label:'Content',type:'textarea'},{key:'output_path',label:'Output Path',type:'text'}],
            dest_folder: [{key:'path',label:'Destination Path',type:'text',default:'drop_folders/output'},{key:'rename',label:'Rename To',type:'text'}],
        };
        return fields[nodeType] || [];
    }

    toJSON() {
        return {
            name: this.workflowName,
            nodes: this.nodes,
            connections: this.connections,
            variables: this.variables,
        };
    }
}
