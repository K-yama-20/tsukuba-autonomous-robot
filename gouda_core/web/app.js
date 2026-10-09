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
