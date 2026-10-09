/* GOUDA MONITOR page logic (stage 5-2). Displays only what the server received; never invents values.
   Connection: SSE /api/events. On (re)connect the latest latched state is fetched (DEC-014, TS-10). A broken link is
   shown as LINK LOST and is not a stop trigger. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const fmtT = (t) => (t == null ? '—' : new Date(t * 1000).toLocaleTimeString('ja-JP', { hour12: false }));
  const fmtAge = (a) => (a == null ? '—' : a < 60 ? a.toFixed(1) + ' s' : (a / 60).toFixed(1) + ' min');
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let lastState = null;

  // ---- tabs (server-side state survives tab changes; the page keeps only which tab is open) ----
  document.querySelectorAll('.tab').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((x) => x.classList.toggle('active', x === b));
    document.querySelectorAll('.tabpane').forEach((p) => p.classList.toggle('active', p.dataset.pane === b.dataset.tab));
    if (b.dataset.tab === 'config') loadConfig();
  }));

  // ---- commands ----
  document.querySelectorAll('button[data-cmd]').forEach((b) => b.addEventListener('click', async () => {
    const name = b.dataset.cmd; b.classList.add('busy'); b.disabled = true;
    const body = name === 'start_autonomy' ? { request_id: 'ui-' + Date.now() } : {};
    try {
      const r = await fetch('/api/command/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await r.json();
      flashCommand(name, j.ok, j.message);
    } catch (e) {
      flashCommand(name, false, 'request failed: ' + e);
    } finally { b.classList.remove('busy'); b.disabled = false; }
  }));
  function flashCommand(name, ok, message) {
    const el = $('commands'); const row = document.createElement('div');
    row.className = 'ev ' + (ok ? '' : 'refused'); row.innerHTML = `<span class="t">${fmtT(Date.now() / 1000)}</span><span class="m"><span class="code">${esc(name)}</span>${esc(message)}</span><span class="n">${ok ? 'OK' : 'NG'}</span>`;
    el.prepend(row);
  }

  // ---- rendering ----
  function kvTable(el, obj, order) {
    const keys = order || Object.keys(obj);
    el.innerHTML = keys.filter((k) => k in obj).map((k) => `<tr><td>${esc(k)}</td><td>${esc(obj[k])}</td></tr>`).join('') || '<tr><td colspan="2" class="amber">NOT_RECEIVED — 未受信（OK とは表示しない）</td></tr>';
  }
  function statusClass(f) { return f.status === 'RECEIVED' ? 'ok' : f.status === 'STALE' ? 'amber' : 'amber'; }
  function render(s) {
    lastState = s;
    const m = s.mode, f = m.freshness;
    $('mode-name').textContent = f.status === 'NOT_RECEIVED' ? 'NOT_RECEIVED' : m.name;
    $('mode-name').className = 'v ' + (f.status === 'NOT_RECEIVED' ? 'amber' : m.code === 4 ? 'amber' : 'cyan');
    $('mode-label').textContent = f.status === 'NOT_RECEIVED' ? '未受信' : m.label;
    $('proc-state').textContent = m.fields.processing_state || '—';
    $('state-rev').textContent = m.fields.state_revision != null ? m.fields.state_revision : '—';
    $('mode-age').textContent = fmtAge(f.age_s); $('mode-age').title = f.verdict;
    kvTable($('mode-table'), Object.assign({}, m.fields, { freshness: f.status, age_s: f.age_s == null ? '—' : f.age_s.toFixed(1), verdict: f.verdict }),
      ['freshness', 'age_s', 'verdict', 'mode', 'processing_state', 'run_id', 'remaining_waypoints', 'current_section', 'stop_reason', 'speed_limit_application_state', 'previous_mode', 'human_pause_or_end_recorded', 'initial_pose_required', 'state_revision']);
    // record
    const r = s.record, rf = r.freshness;
    const logActive = r.fields.log_active === 'True', bagActive = r.fields.rosbag_active === 'True';
    $('rec-short').textContent = rf.status === 'NOT_RECEIVED' ? 'NOT_RECEIVED' : `LOG ${logActive ? 'ON' : 'OFF'} / BAG ${bagActive ? 'ON' : 'OFF'}`;
    $('rec-short').className = 'v ' + (rf.status === 'NOT_RECEIVED' ? 'amber' : 'cyan');
    $('log-status').textContent = rf.status === 'NOT_RECEIVED' ? 'NOT_RECEIVED' : (logActive ? 'ACTIVE' : 'STOPPED') + (r.fields.auto_started_by ? ' (auto: ' + r.fields.auto_started_by + ')' : '');
    $('log-status').className = 'status ' + (rf.status === 'NOT_RECEIVED' ? 'amber' : logActive ? 'ok' : '');
    $('bag-status').textContent = rf.status === 'NOT_RECEIVED' ? 'NOT_RECEIVED' : bagActive ? 'ACTIVE' : 'STOPPED';
    $('bag-status').className = 'status ' + (rf.status === 'NOT_RECEIVED' ? 'amber' : bagActive ? 'ok' : '');
    kvTable($('record-table'), Object.assign({}, r.fields, { freshness: rf.status, age_s: rf.age_s == null ? '—' : rf.age_s.toFixed(1) }),
      ['freshness', 'age_s', 'log_active', 'log_started_by', 'auto_started_by', 'rosbag_active', 'rosbag_started_by', 'session_dir', 'last_gap', 'failures', 'status_revision', 'message']);
    // esp32 (nothing until stage 5-5)
    const e = s.esp32;
    $('esp32-status').textContent = e.freshness.status; $('esp32-status').className = 'status ' + statusClass(e.freshness);
    kvTable($('esp32-table'), Object.keys(e.fields).length ? e.fields : {});
    $('esp32-note').textContent = e.note || e.freshness.verdict;
    // pc / nodes
    const n = s.nodes;
    $('node-count').textContent = n.names.length ? String(n.names.length) : '—';
    $('pc-status').textContent = n.at ? `${n.names.length} nodes, age ${fmtAge(n.age_s)}` : 'NOT_RECEIVED';
    $('pc-status').className = 'status ' + (n.at ? 'ok' : 'amber');
    $('nodes').innerHTML = n.names.map((x) => `<span>${esc(x)}</span>`).join('') || '<span class="amber">—</span>';
    $('pc-note').textContent = 'node 一覧は ROS graph から取得（表示のみ。停止条件ではない）。lifecycle 状態・/diagnostics の表示は後の工程。';
    // external displays
    for (const [key, id] of [['navigation', 'nav'], ['lidar_localization', 'lidar']]) {
      const x = s.external_displays[key];
      $('ext-' + id + '-status').textContent = x.status; $('ext-' + id + '-note').textContent = x.note;
    }
    // events
    $('events-count').textContent = s.events.length ? `${s.events.length} kinds` : '';
    $('events').innerHTML = s.events.map((ev) => {
      let d = {}; try { d = JSON.parse(ev.details || '{}'); } catch (_) { /* keep raw */ }
      const refused = d.accepted === false; const cls = refused ? 'refused' : '';
      return `<div class="ev ${cls}"><span class="t">${fmtT(ev.last_at)}</span><span class="m"><span class="code">${esc(ev.transition_id || ev.event)}</span>${esc(ev.reason)}</span><span class="n">×${ev.count}</span></div>`;
    }).join('') || '<div class="dim">未受信</div>';
    // commands (server-side log, merged with local flashes)
    if (s.commands.length) {
      $('commands').innerHTML = s.commands.map((c) => `<div class="ev ${c.ok ? '' : 'refused'}"><span class="t">${fmtT(c.t)}</span><span class="m"><span class="code">${esc(c.command)}</span>${esc(c.message)}</span><span class="n">${c.ok ? 'OK' : 'NG'}</span></div>`).join('');
    }
    wpFillMaps(s);
    // map database (IFD-29)
    if (s.maps) {
      const rows = {};
      (s.maps.origins || []).forEach((o) => {
        rows[o.origin_id] = `source ${String(o.source_hash).slice(0, 12)}… submaps ${o.submaps}; converted: ` + ((o.converted || []).map((c) => `rev ${c.revision} ${String(c.content_hash).slice(0, 12)}…`).join(', ') || 'なし');
      });
      kvTable($('maps-table'), rows); $('maps-note').textContent = s.maps.note || `${(s.maps.origins || []).length} origin(s)`;
    }
    // settings (UI parameters of the relay node)
    if (s.settings && s.settings.ui) kvTable($('settings-table'), Object.assign({}, s.settings.ui, { declared_by: s.settings.declared_by, source: s.settings.source, auto_retry: s.settings.auto_retry }));
    // pop-up for a failed automatic log start (DEC-071). Only events newer than the last seen one trigger it; a
    // retained message received on (re)connect is not a trigger (DEC-072).
    const failed = s.events.filter((ev) => ev.event === 'record_auto_start_failed' || ev.event === 'record_auto_stop_failed');
    const newest = failed.reduce((m, ev) => Math.max(m, ev.last_at), 0);
    if (seenEventsBaseline !== null && newest > seenEventsBaseline) {
      const ev = failed.find((x) => x.last_at === newest);
      $('popup-body').textContent = `${fmtT(ev.last_at)} ${ev.transition_id || ''} ${ev.reason}\n走行は止めない。記録が必要なら Record ボタンで手動開始する。`;
      $('popup').hidden = false;
    }
    if (seenEventsBaseline === null || newest > seenEventsBaseline) seenEventsBaseline = newest;
    $('clock').textContent = 'server ' + fmtT(s.now);
  }
  let seenEventsBaseline = null;   // set from the first snapshot after connect: retained history is not a trigger
  $('popup-ack').addEventListener('click', () => { $('popup').hidden = true; });

  // ---- /config ----
  async function loadConfig() {
    const r = await fetch('/api/config'); const c = await r.json(); renderConfig(c);
  }
  function renderConfig(c) {
    $('config-rev').textContent = `revision ${c.config_revision} / UNKNOWN ${c.unknown_count}/${Object.keys(c.values).length} / ${c.path}`;
    const form = $('config-form');
    form.innerHTML = Object.keys(c.values).map((k) => {
      const v = c.values[k]; const unknown = v === 'UNKNOWN';
      return `<label>${esc(k)} <span class="dim">(${esc(c.kinds[k])})</span><input name="${esc(k)}" class="${unknown ? 'unknown' : ''}" value="${esc(v)}" placeholder="UNKNOWN"></label>`;
    }).join('');
  }
  $('config-save').addEventListener('click', async () => {
    const data = {}; new FormData($('config-form')).forEach((v, k) => { data[k] = v; });
    const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const j = await r.json(); $('config-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message; $('config-msg').className = j.ok ? 'cyan' : 'amber';
    if (j.config) renderConfig(j.config);
  });

  // ---- waypoint_manager (IFD-30 / IFD-41): edits on the converted map; save generates the speed mask ----
  const wpState = { map: null, geom: null, img: null, points: [], limits: [], scale: 1 };
  function wpFillMaps(s) {
    const sel = $('wp-map-select'); const cur = sel.value; sel.innerHTML = '';
    (s.maps && s.maps.origins || []).forEach((o) => (o.converted || []).forEach((c) => {
      const opt = document.createElement('option'); opt.value = `${o.origin_id}/${c.revision}`; opt.textContent = `${o.origin_id} rev ${c.revision} (${String(c.content_hash).slice(0, 8)}…)`; sel.appendChild(opt);
    }));
    if (cur) sel.value = cur;
    if (s.mask_params) {
      if (s.mask_params.half_width_m != null && !$('wp-half-width').value) $('wp-half-width').value = s.mask_params.half_width_m;
      if (s.mask_params.step_mps != null && !$('wp-step').value) $('wp-step').value = s.mask_params.step_mps;
    }
    if (s.routes) {
      const rows = {};
      (s.routes.sets || []).forEach((st) => st.revisions.forEach((r) => { rows[`${st.set_id}/${r.revision}`] = `${r.waypoints} pts, map ${r.map.origin_id}/${r.map.revision}, ${r.warnings} warning(s), ${String(r.content_hash).slice(0, 10)}…`; }));
      kvTable($('wp-routes'), rows);
    }
  }
  async function wpLoadMap() {
    const v = $('wp-map-select').value; if (!v) { $('wp-map-status').textContent = '変換後地図がない'; return; }
    const [origin, rev] = v.split('/');
    const g = await (await fetch(`/api/map/${origin}/${rev}/geometry.json`)).json();
    if (!g.ok) { $('wp-map-status').textContent = g.message; return; }
    const img = new Image(); img.src = `/api/map/${origin}/${rev}/map.png?t=${Date.now()}`;
    img.onload = () => { wpState.map = { origin, rev: parseInt(rev, 10), hash: g.content_hash }; wpState.geom = g; wpState.img = img; wpState.points = []; wpState.limits = []; wpDraw(); $('wp-map-status').textContent = `${g.width}x${g.height} @ ${g.resolution} m`; $('wp-map-status').className = 'status ok'; };
    img.onerror = () => { $('wp-map-status').textContent = '地図画像を取得できない'; };
  }
  function wpDraw() {
    const cv = $('wp-canvas'); const ctx = cv.getContext('2d'); const g = wpState.geom;
    if (!g || !wpState.img) { ctx.clearRect(0, 0, cv.width, cv.height); return; }
    const scale = Math.min(cv.width / g.width, cv.height / g.height); wpState.scale = scale;
    ctx.fillStyle = '#03100f'; ctx.fillRect(0, 0, cv.width, cv.height);
    ctx.imageSmoothingEnabled = false; ctx.drawImage(wpState.img, 0, 0, g.width * scale, g.height * scale);
    const toPx = (p) => [ (p.x - g.origin_x) / g.resolution * scale, (g.height - (p.y - g.origin_y) / g.resolution) * scale ];
    ctx.lineWidth = 2; ctx.strokeStyle = '#39d5e0';
    wpState.points.forEach((p, i) => { const [px, py] = toPx(p); if (i > 0) { const [qx, qy] = toPx(wpState.points[i - 1]); ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(px, py); ctx.stroke(); } });
    wpState.points.forEach((p, i) => { const [px, py] = toPx(p); ctx.fillStyle = i === 0 ? '#f0b43c' : '#39d5e0'; ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill(); ctx.fillStyle = '#a8e6ea'; ctx.font = '11px monospace'; ctx.fillText(String(i), px + 6, py - 6); });
    wpTable();
  }
  function wpTable() {
    const rows = wpState.points.slice(0, -1).map((p, i) => `<tr><td>区間 ${i}→${i + 1}</td><td><input class="sec" data-i="${i}" value="${wpState.limits[i] != null ? wpState.limits[i] : ''}" placeholder="m/s"></td></tr>`).join('');
    $('wp-table').innerHTML = rows || '<tr><td colspan="2" class="dim">waypoint を 2 点以上置く</td></tr>';
    $('wp-table').querySelectorAll('input.sec').forEach((inp) => inp.addEventListener('change', () => { wpState.limits[parseInt(inp.dataset.i, 10)] = parseFloat(inp.value); }));
  }
  $('wp-canvas').addEventListener('click', (ev) => {
    const g = wpState.geom; if (!g) return;
    const r = $('wp-canvas').getBoundingClientRect(); const px = (ev.clientX - r.left) * ($('wp-canvas').width / r.width); const py = (ev.clientY - r.top) * ($('wp-canvas').height / r.height);
    const x = g.origin_x + px / wpState.scale * g.resolution; const y = g.origin_y + (g.height - py / wpState.scale) * g.resolution;
    wpState.points.push({ x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000, yaw: 0, kind: 'pass' });
    if (wpState.points.length > 1) wpState.limits.push(wpState.limits.length ? wpState.limits[wpState.limits.length - 1] : null);
    wpDraw();
  });
  $('wp-load-map').addEventListener('click', wpLoadMap);
  $('wp-undo').addEventListener('click', () => { wpState.points.pop(); wpState.limits.pop(); wpDraw(); });
  $('wp-clear').addEventListener('click', () => { wpState.points = []; wpState.limits = []; wpDraw(); });
  $('wp-save').addEventListener('click', async () => {
    if (!wpState.map) { $('wp-msg').textContent = 'NG: 地図を表示してから編集する'; return; }
    const body = { set_id: $('wp-set-id').value || '', half_width_m: $('wp-half-width').value, step_mps: $('wp-step').value,
      set: { map: { origin_id: wpState.map.origin, revision: wpState.map.rev, content_hash: wpState.map.hash }, waypoints: wpState.points, section_limits_mps: wpState.limits } };
    const r = await fetch('/api/waypoints/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const j = await r.json(); $('wp-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message; $('wp-msg').className = j.ok ? 'note cyan' : 'note amber';
    $('wp-warnings').innerHTML = (j.warnings || []).map((w) => `<div class="ev refused"><span class="t">区間 ${w.sections.join('/')}</span><span class="m">${esc(w.message)}</span><span class="n">${w.cells} cell</span></div>`).join('') || '<div class="dim">なし</div>';
    if (j.ok) { $('wp-set-id').value = j.set_id; }
  });

  // ---- link (SSE with reconnect; current latched state is fetched on every connect) ----
  let es = null;
  function setLink(text, cls) { $('link-state').textContent = text; $('link-state').className = 'v ' + cls; }
  async function fetchState() {
    try { const r = await fetch('/api/state'); render(await r.json()); } catch (_) { /* link handling below */ }
  }
  function connect() {
    if (es) es.close();
    setLink('CONNECTING', 'amber');
    es = new EventSource('/api/events');
    es.addEventListener('open', () => { setLink('ONLINE', 'cyan'); fetchState(); });
    es.addEventListener('state', (ev) => { try { render(JSON.parse(ev.data)); } catch (e) { /* ignore malformed */ } });
    es.addEventListener('error', () => { setLink('LINK LOST — 再接続中（停止契機ではない）', 'amber'); });
  }
  connect();
  // keep ages moving between pushes (display only)
  setInterval(() => { if (lastState) { const s = lastState; const dt = Date.now() / 1000 - s.now; if (s.mode.freshness.age_s != null) $('mode-age').textContent = fmtAge(s.mode.freshness.age_s + dt); } }, 1000);
})();
