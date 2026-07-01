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
        this.workflowProps = {};
        this.variables = [];
        this.initEvents();
    }

    initEvents() {
        this.canvas.addEventListener('mousedown', e => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', e => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', e => this.onMouseUp(e));
        this.canvas.addEventListener('contextmenu', e => e.preventDefault());
        this.canvas.addEventListener('dblclick', e => this.onDblClick(e));
        window.addEventListener('resize', () => this.resize());
        const ro = new ResizeObserver(() => this.resize());
        ro.observe(this.canvas.parentElement);
        this.canvas.addEventListener('dragover', e => e.preventDefault());
        this.canvas.addEventListener('drop', e => {
            e.preventDefault();
            const type = e.dataTransfer.getData('text/plain');
            const name = e.dataTransfer.getData('application/name');
            if (type) {
                const rect = this.canvas.getBoundingClientRect();
                this.addNode(type, e.clientX - rect.left, e.clientY - rect.top, name || type);
            }
        });
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
        this.workflowProps = {
            description: wf.description || '',
            work_folder: wf.work_folder || '',
            sleep_timer: wf.sleep_timer || 10,
            cron: wf.cron || '',
            priority: wf.priority || 2,
            timeout_level: wf.timeout_level || 3,
            active_on: wf.active_on || ['mon','tue','wed','thu','fri','sat','sun'],
        };
        this.nodes = (wf.nodes || []).map(n => typeof n === 'string' ? JSON.parse(n) : n);
        this.connections = (wf.connections || []).map(c => typeof c === 'string' ? JSON.parse(c) : c);
        this.variables = wf.variables || [];
        this.draw();
    }

    addNode(type, x, y, name) {
        const id = 'n' + Date.now().toString(36) + Math.random().toString(36).substr(2,4);
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
            if (x >= n.x && x <= n.x + 160 && y >= n.y && y <= n.y + 60) return n;
        }
        return null;
    }

    getPortPos(node, port) {
        if (port === 'output' || port === 'error') {
            return {x: node.x + 160, y: node.y + 30};
        }
        return {x: node.x, y: node.y + 30};
    }

    onMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
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
        this.dragging = null;
    }

    onDblClick(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const node = this.getNodeAt(x, y);
        if (node) this.selectNode(node);
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
            const stateColors = {idle:'#2d2d44',running:'#0f3460',completed:'#1b5e20',failed:'#b71c1c',skipped:'#555',paused:'#e65100'};
            ctx.fillStyle = stateColors[n.state] || '#2d2d44';
            ctx.strokeStyle = selected ? '#e94560' : '#555';
            ctx.lineWidth = selected ? 2.5 : 1;

            const w = 160, h = 60;
            ctx.beginPath();
            ctx.roundRect(n.x, n.y, w, h, 4);
            ctx.fill();
            ctx.stroke();

            ctx.fillStyle = '#fff';
            ctx.font = 'bold 11px sans-serif';
            ctx.fillText((n.name || n.node_type).substring(0,18), n.x + 8, n.y + 22);
            ctx.fillStyle = '#999';
            ctx.font = '9px sans-serif';
            ctx.fillText(n.node_type, n.x + 8, n.y + 40);

            const cat = n.node_type.split('_')[0];
            const catColors = {mon:'#2196f3',dec:'#ff9800',enc:'#4caf50',avs:'#9c27b0',av:'#9c27b0',op:'#f44336',cmd:'#ff5722',other:'#795548',dest:'#00bcd4'};
            ctx.fillStyle = catColors[cat] || '#666';
            ctx.beginPath();
            ctx.arc(n.x + w - 12, n.y + 12, 5, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#e94560';
            ctx.beginPath();
            ctx.arc(n.x, n.y + 30, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#4caf50';
            ctx.beginPath();
            ctx.arc(n.x + w, n.y + 30, 5, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#f44336';
            ctx.beginPath();
            ctx.arc(n.x + w, n.y + 48, 4, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    showProperties(node) {
        const panel = document.getElementById('properties-panel');
        if (!node) {
            panel.innerHTML = `<h3>Workflow Properties</h3>
                <div class="prop-group"><label>Name</label><input id="wf-name" value="${this.workflowName}" onchange="editor.setWfProp('name',this.value)"></div>
                <div class="prop-group"><label>Description</label><textarea id="wf-desc" rows="2" onchange="editor.setWfProp('description',this.value)">${this.workflowProps.description||''}</textarea></div>
                <div class="prop-group"><label>Work Folder</label><input id="wf-workfolder" value="${this.workflowProps.work_folder||''}" onchange="editor.setWfProp('work_folder',this.value)"></div>
                <div class="prop-group"><label>Sleep Timer (s)</label><input type="number" id="wf-sleep" value="${this.workflowProps.sleep_timer||10}" onchange="editor.setWfProp('sleep_timer',this.value)"></div>
                <div class="prop-group"><label>Cron Schedule</label><input id="wf-cron" value="${this.workflowProps.cron||''}" placeholder="e.g. */5 * * * *" onchange="editor.setWfProp('cron',this.value)"></div>
                <div class="prop-group"><label>Priority (0-5)</label><input type="number" id="wf-priority" min="0" max="5" value="${this.workflowProps.priority||2}" onchange="editor.setWfProp('priority',this.value)"></div>
                <div class="prop-group"><label>Timeout Level (s)</label><input type="number" id="wf-timeout" value="${this.workflowProps.timeout_level||3}" onchange="editor.setWfProp('timeout_level',this.value)"></div>
                <div class="prop-group"><label>Active Days</label><div id="wf-days" class="checkbox-group">${['mon','tue','wed','thu','fri','sat','sun'].map(d=>`<label class="checkbox"><input type="checkbox" value="${d}" ${(this.workflowProps.active_on||[]).includes(d)?'checked':''} onchange="editor.toggleActiveDay('${d}')">${d}</label>`).join('')}</div></div>
                <hr>
                <h4>Workflow Variables</h4>
                <div id="wf-vars-list">${this.variables.map((v,i)=>`<div class="var-row"><input value="${v.name||''}" placeholder="name" onchange="editor.updateVar(${i},'name',this.value)"><input value="${v.value||''}" placeholder="value" onchange="editor.updateVar(${i},'value',this.value)"><button class="btn btn-danger btn-xs" onclick="editor.removeVar(${i})">X</button></div>`).join('')}</div>
                <button class="btn btn-sm" onclick="editor.addVar()">+ Add Variable</button>`;
            return;
        }

        const paramFields = this.getParamFields(node.node_type);
        let html = `<h3>${node.name || node.node_type}</h3>
            <div class="prop-group"><label>Name</label><input id="prop-name" value="${node.name||''}" onchange="editor.updateNodeProp('name',this.value)"></div>`;

        paramFields.forEach(f => {
            const val = node.params[f.key] !== undefined ? node.params[f.key] : (f.default || '');
            if (f.type === 'select') {
                const opts = f.options.map(o => `<option value="${o}" ${String(val)===String(o)?'selected':''}>${o}</option>`).join('');
                html += `<div class="prop-group"><label>${f.label}</label><select id="prop-${f.key}" onchange="editor.updateNodeParam('${f.key}',this.value)">${opts}</select></div>`;
            } else if (f.type === 'textarea') {
                html += `<div class="prop-group"><label>${f.label}</label><textarea id="prop-${f.key}" rows="3" onchange="editor.updateNodeParam('${f.key}',this.value)">${val}</textarea></div>`;
            } else if (f.type === 'checkbox') {
                html += `<div class="prop-group"><label>${f.label}</label><input type="checkbox" id="prop-${f.key}" ${val?'checked':''} onchange="editor.updateNodeParam('${f.key}',this.checked)"></div>`;
            } else {
                html += `<div class="prop-group"><label>${f.label}</label><input id="prop-${f.key}" value="${val}" onchange="editor.updateNodeParam('${f.key}',this.value)"></div>`;
            }
        });

        if (node.node_type === 'op_cond') {
            html += this._buildConditionEditor(node);
        } else if (node.node_type === 'op_populate') {
            html += this._buildPopulateEditor(node);
        }

        html += `<div style="margin-top:15px"><button class="btn btn-danger btn-sm" onclick="editor.removeNode('${node.id}')">Delete Node</button></div>`;
        panel.innerHTML = html;
    }

    _buildConditionEditor(node) {
        const exprs = node.params.expressions || [];
        let html = '<div class="condition-editor"><h4>Condition Expressions</h4>';
        for (let i = 0; i < 8; i++) {
            const e = exprs[i] || {};
            html += `<div class="condition-row">
                <select onchange="editor.updateCondition(${i},'and_or',this.value)">
                    <option value="and" ${e.and_or!=='or'?'selected':''}>AND</option>
                    <option value="or" ${e.and_or==='or'?'selected':''}>OR</option>
                </select>
                <input value="${e.variable||''}" placeholder="%var%" onchange="editor.updateCondition(${i},'variable',this.value)" style="width:100px">
                <select onchange="editor.updateCondition(${i},'operator',this.value)">
                    ${['=','==','!=','>','<','>=','<=','contains','exists'].map(op=>`<option value="${op}" ${e.operator===op?'selected':''}>${op}</option>`).join('')}
                </select>
                <input value="${e.value||''}" placeholder="value" onchange="editor.updateCondition(${i},'value',this.value)" style="width:100px">
            </div>`;
        }
        html += '</div>';
        return html;
    }

    _buildPopulateEditor(node) {
        const assigns = node.params.assignments || [];
        let html = '<div class="populate-editor"><h4>Variable Assignments</h4>';
        for (let i = 0; i < 8; i++) {
            const a = assigns[i] || {};
            html += `<div class="populate-row">
                <input value="${a.variable||''}" placeholder="%var_name%" onchange="editor.updatePopulate(${i},'variable',this.value)" style="width:120px">
                <span>=</span>
                <input value="${a.value||''}" placeholder="value or %var% + 10" onchange="editor.updatePopulate(${i},'value',this.value)" style="width:150px">
            </div>`;
        }
        html += '</div>';
        return html;
    }

    updateCondition(row, key, val) {
        if (!this.selectedNode) return;
        if (!this.selectedNode.params.expressions) this.selectedNode.params.expressions = [];
        while (this.selectedNode.params.expressions.length <= row) {
            this.selectedNode.params.expressions.push({variable:'', operator:'=', value:'', and_or:'and'});
        }
        this.selectedNode.params.expressions[row][key] = val;
    }

    updatePopulate(row, key, val) {
        if (!this.selectedNode) return;
        if (!this.selectedNode.params.assignments) this.selectedNode.params.assignments = [];
        while (this.selectedNode.params.assignments.length <= row) {
            this.selectedNode.params.assignments.push({variable:'', value:''});
        }
        this.selectedNode.params.assignments[row][key] = val;
    }

    setWfProp(key, val) {
        if (key === 'name') this.workflowName = val;
        else this.workflowProps[key] = val;
    }

    toggleActiveDay(day) {
        if (!this.workflowProps.active_on) this.workflowProps.active_on = [];
        const idx = this.workflowProps.active_on.indexOf(day);
        if (idx >= 0) this.workflowProps.active_on.splice(idx, 1);
        else this.workflowProps.active_on.push(day);
    }

    addVar() {
        this.variables.push({name:'', value:'', vtype:'s'});
        this.showProperties(this.selectedNode);
    }

    updateVar(idx, key, val) {
        this.variables[idx][key] = val;
    }

    removeVar(idx) {
        this.variables.splice(idx, 1);
        this.showProperties(this.selectedNode);
    }

    updateNodeProp(key, val) {
        if (this.selectedNode) { this.selectedNode[key] = val; this.draw(); }
    }

    updateNodeParam(key, val) {
        if (this.selectedNode) {
            this.selectedNode.params = this.selectedNode.params || {};
            this.selectedNode.params[key] = val;
        }
    }

    addConnection(fromId, toId, fromPort, toPort) {
        this.connections.push({from_node:fromId, to_node:toId, from_port:fromPort||'output', to_port:toPort||'input'});
        this.draw();
    }

    getParamFields(nodeType) {
        const fields = {
            mon_folder: [
                {key:'path',label:'Watch Path',type:'text',default:'drop_folders/input'},
                {key:'accept_filter',label:'Accept Filter (*.*)',type:'text',default:'*.*'},
                {key:'deny_filter',label:'Deny Filter',type:'text'},
                {key:'deny_folders',label:'Deny Folders',type:'text'},
                {key:'create_folder',label:'Create Folder',type:'checkbox'},
                {key:'recurse',label:'Recursive',type:'checkbox'},
                {key:'localize_file',label:'Localize File',type:'checkbox'},
                {key:'check_growing',label:'Check Growing',type:'select',options:['once','continuously','never'],default:'once'},
                {key:'forget_missing',label:'Forget Missing',type:'checkbox'},
                {key:'limit_file_size',label:'Min File Size (bytes)',type:'text',default:'0'},
                {key:'rebuild_history',label:'Rebuild History',type:'checkbox'},
                {key:'clear_history',label:'Clear History',type:'checkbox'},
                {key:'poll_interval',label:'Poll Interval (s)',type:'text',default:'2'},
            ],
            mon_sequence: [
                {key:'path',label:'Sequence Path',type:'text'},
                {key:'pattern',label:'Pattern',type:'text',default:'%04d'},
                {key:'start',label:'Start Frame',type:'text',default:'0'},
                {key:'end',label:'End Frame',type:'text',default:'100'},
                {key:'extension',label:'Extension',type:'text',default:'dpx'},
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
            dec_youtube: [
                {key:'url',label:'URL',type:'text'},
                {key:'output_dir',label:'Output Directory',type:'text'},
            ],
            enc_av_mp4: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'vcodec',label:'Video Codec',type:'select',options:['libx264','libx265','copy'],default:'libx264'},
                {key:'video_width',label:'Video Width',type:'text'},
                {key:'video_height',label:'Video Height',type:'text'},
                {key:'resize_method',label:'Resize Method',type:'select',options:['stretch','fit','fill'],default:'stretch'},
                {key:'video_bitrate',label:'Video Bitrate',type:'text'},
                {key:'crf',label:'CRF',type:'text',default:'23'},
                {key:'video_preset',label:'Preset',type:'select',options:['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'],default:'medium'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv420p','yuv422p','yuv444p','yuv420p10le'],default:'yuv420p'},
                {key:'video_profile',label:'Profile',type:'select',options:['baseline','main','high','high10'],default:'high'},
                {key:'level',label:'Level',type:'select',options:['3.0','3.1','4.0','4.1','5.0','5.1'],default:'4.1'},
                {key:'framerate',label:'Frame Rate',type:'text'},
                {key:'video_range',label:'Video Range',type:'select',options:['limited','full'],default:'limited'},
                {key:'faststart',label:'FastStart',type:'checkbox'},
                {key:'deinterlace',label:'Deinterlace',type:'checkbox'},
                {key:'acodec',label:'Audio Codec',type:'select',options:['aac','mp3','copy','none'],default:'aac'},
                {key:'audio_bitrate',label:'Audio Bitrate',type:'text',default:'192k'},
                {key:'audio_sample_rate',label:'Sample Rate',type:'select',options:['44100','48000','96000'],default:'48000'},
                {key:'audio_channels',label:'Channels',type:'select',options:['1','2','6','8'],default:'2'},
                {key:'custom_x264_options',label:'Custom x264 Options',type:'text'},
            ],
            enc_av_265: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'video_width',label:'Video Width',type:'text'},
                {key:'video_height',label:'Video Height',type:'text'},
                {key:'resize_method',label:'Resize Method',type:'select',options:['stretch','fit','fill'],default:'stretch'},
                {key:'crf',label:'CRF',type:'text',default:'28'},
                {key:'video_preset',label:'Preset',type:'select',options:['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'],default:'medium'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv420p','yuv420p10le','yuv422p10le'],default:'yuv420p'},
                {key:'framerate',label:'Frame Rate',type:'text'},
                {key:'hdr',label:'HDR (BT.2020)',type:'checkbox'},
                {key:'acodec',label:'Audio Codec',type:'select',options:['aac','mp3','copy','none'],default:'aac'},
                {key:'audio_bitrate',label:'Audio Bitrate',type:'text',default:'192k'},
                {key:'custom_x265_options',label:'Custom x265 Options',type:'text'},
            ],
            enc_av_prores: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'profile',label:'Profile',type:'select',options:['0','1','2','3','4','5'],default:'3'},
                {key:'pixel_format',label:'Pixel Format',type:'select',options:['yuv422p','yuv422p10le','yuv444p','yuv444p10le'],default:'yuv422p10le'},
            ],
            enc_av_dnxhr: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'dnxhr_profile',label:'Profile',type:'select',options:['DNxHR LB','DNxHR SQ','DNxHR HQ','DNxHR HQX','DNxHR 444'],default:'DNxHR HQ'},
            ],
            enc_av_dnxhd: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'dnxhd_profile',label:'Profile',type:'select',options:['DNxHD 120','DNxHD 185','DNxHD 36','DNxHD 45'],default:'DNxHD 185'},
            ],
            enc_av_xdcamhd: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'video_bitrate',label:'Bitrate',type:'text',default:'50M'},
            ],
            enc_av_av1: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'crf',label:'CRF',type:'text',default:'30'},
                {key:'video_preset',label:'Preset (0-13)',type:'text',default:'4'},
            ],
            enc_av_customff: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'ffmpeg_args',label:'FFmpeg Arguments',type:'textarea'},
            ],
            enc_a_audio: [
                {key:'input',label:'Input Override',type:'text'},
                {key:'output',label:'Output File',type:'text'},
                {key:'acodec',label:'Audio Codec',type:'select',options:['pcm_s16le','pcm_s24le','pcm_s32le','aac','mp3','flac'],default:'pcm_s16le'},
                {key:'audio_sample_rate',label:'Sample Rate',type:'select',options:['44100','48000','96000'],default:'48000'},
                {key:'audio_channels',label:'Channels',type:'select',options:['1','2','6','8'],default:'2'},
            ],
            avs_v_resize: [
                {key:'width',label:'Width',type:'text',default:'1920'},
                {key:'height',label:'Height',type:'text',default:'1080'},
                {key:'interpolation',label:'Algorithm',type:'select',options:['lanczos','bilinear','bicubic'],default:'lanczos'},
            ],
            avs_v_crop: [
                {key:'x',label:'X',type:'text',default:'0'},
                {key:'y',label:'Y',type:'text',default:'0'},
                {key:'width',label:'Width',type:'text',default:'1920'},
                {key:'height',label:'Height',type:'text',default:'1080'},
            ],
            avs_v_color: [
                {key:'brightness',label:'Brightness',type:'text',default:'0'},
                {key:'contrast',label:'Contrast',type:'text',default:'1'},
                {key:'saturation',label:'Saturation',type:'text',default:'1'},
                {key:'gamma',label:'Gamma',type:'text',default:'1'},
            ],
            avs_v_watermark: [
                {key:'watermark_path',label:'Watermark Image',type:'text'},
                {key:'position',label:'Position',type:'select',options:['top_left','top_right','bottom_left','bottom_right','center'],default:'top_right'},
            ],
            avs_v_tc: [
                {key:'text',label:'Text',type:'text',default:'%s_datetime%'},
                {key:'position',label:'Position',type:'select',options:['top_left','top_right','bottom_left','bottom_right'],default:'bottom_right'},
                {key:'fontsize',label:'Font Size',type:'text',default:'24'},
                {key:'fontcolor',label:'Font Color',type:'text',default:'white'},
            ],
            avs_v_deinterlace: [{key:'mode',label:'Mode',type:'select',options:['bob','weave'],default:'bob'}],
            avs_v_pad: [
                {key:'width',label:'Width',type:'text',default:'1920'},
                {key:'height',label:'Height',type:'text',default:'1080'},
                {key:'color',label:'Color',type:'select',options:['black','white'],default:'black'},
            ],
            avs_v_flip: [{key:'direction',label:'Direction',type:'select',options:['horizontal','vertical'],default:'horizontal'}],
            avs_v_fpsconv: [
                {key:'target_fps',label:'Target FPS',type:'text',default:'25'},
                {key:'algorithm',label:'Algorithm',type:'select',options:['mci','blend','direct'],default:'mci'},
            ],
            avs_v_reverse: [],
            avs_av_fade: [
                {key:'fade_type',label:'Type',type:'select',options:['in','out'],default:'in'},
                {key:'duration',label:'Duration (s)',type:'text',default:'2'},
                {key:'start',label:'Start (s)',type:'text',default:'0'},
            ],
            op_cond: [
                {key:'dispel_on_false',label:'Dispel on False',type:'checkbox'},
            ],
            op_populate: [],
            op_analyzer: [{key:'input',label:'Input File',type:'text'}],
            op_foreach: [
                {key:'variable',label:'Variable Name',type:'text',default:'s_item'},
                {key:'items',label:'Items (| separated)',type:'text'},
                {key:'delimiter',label:'Delimiter',type:'text',default:'|'},
            ],
            op_hold: [{key:'seconds',label:'Seconds',type:'text',default:'5'}],
            cmd_run: [
                {key:'command',label:'Command',type:'textarea'},
                {key:'timeout',label:'Timeout (s)',type:'text',default:'300'},
                {key:'capture_output',label:'Capture Output',type:'checkbox'},
            ],
            other_email: [
                {key:'smtp_server',label:'SMTP Server',type:'text'},
                {key:'smtp_port',label:'Port',type:'text',default:'587'},
                {key:'from',label:'From',type:'text'},
                {key:'to',label:'To',type:'text'},
                {key:'subject',label:'Subject',type:'text'},
                {key:'body',label:'Body',type:'textarea'},
            ],
            other_httpsend: [
                {key:'url',label:'URL',type:'text'},
                {key:'method',label:'Method',type:'select',options:['GET','POST','PUT','DELETE'],default:'GET'},
                {key:'body',label:'Body (JSON)',type:'textarea'},
            ],
            other_textfile: [
                {key:'content',label:'Content',type:'textarea'},
                {key:'output_path',label:'Output Path',type:'text'},
                {key:'mode',label:'Mode',type:'select',options:['overwrite','append'],default:'overwrite'},
            ],
            dest_folder: [
                {key:'path',label:'Destination Path',type:'text'},
                {key:'prefix',label:'Prefix',type:'text'},
                {key:'suffix',label:'Suffix',type:'text'},
                {key:'overwrite',label:'Overwrite',type:'checkbox'},
                {key:'unique_name',label:'Unique Name',type:'checkbox'},
                {key:'zero_padding',label:'Zero Padding',type:'text',default:'0'},
                {key:'drop_original_name',label:'Drop Original Name',type:'checkbox'},
                {key:'drop_extension',label:'Drop Extension',type:'checkbox'},
                {key:'move_instead_of_copy',label:'Move (not Copy)',type:'checkbox'},
                {key:'force_case',label:'Force Case',type:'select',options:['','lower','upper'],default:''},
            ],
        };
        return fields[nodeType] || [];
    }

    toJSON() {
        return {
            name: this.workflowName,
            description: this.workflowProps.description || '',
            nodes: this.nodes,
            connections: this.connections,
            variables: this.variables,
            work_folder: this.workflowProps.work_folder || '',
            sleep_timer: parseInt(this.workflowProps.sleep_timer) || 10,
            cron: this.workflowProps.cron || '',
            priority: parseInt(this.workflowProps.priority) || 2,
            timeout_level: parseInt(this.workflowProps.timeout_level) || 3,
            active_on: this.workflowProps.active_on || ['mon','tue','wed','thu','fri','sat','sun'],
        };
    }
}
