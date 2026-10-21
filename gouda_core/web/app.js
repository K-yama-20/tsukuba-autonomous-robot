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
    if (b.dataset.tab === 'config') { loadConfig(); loadMotionComp(); }
    if (b.dataset.tab === 'maps') loadMapSettings();
  }));

  // ---- commands ----
  document.querySelectorAll('button[data-cmd]').forEach((b) => b.addEventListener('click', async () => {
    const name = b.dataset.cmd; b.classList.add('busy'); b.disabled = true;
    const body = name === 'start_autonomy' ? autoStartBody() : {};
    try {
      const r = await fetch('/api/command/' + name, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const j = await r.json();
      flashCommand(name, j.ok, j.message);
      if (j.warning) {   // DEC-088: a sensor had no data when 地図作成開始 was pressed (the start itself is not refused)
        $('popup-title').textContent = '地図作成の開始時にセンサーのデータがない';
        $('popup-body').textContent = j.warning; $('popup').hidden = false;
      }
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
      ['freshness', 'age_s', 'log_active', 'log_started_by', 'auto_started_by', 'rosbag_active', 'rosbag_started_by', 'rosbag_output', 'session_dir', 'last_gap', 'failures', 'last_failure', 'status_revision', 'message']);
    // rosbag save progress (DEC-174): shown from the moment the save starts until it ends
    if (rf.status !== 'NOT_RECEIVED') {
      if (r.fields.rosbag_saving === 'True') {
        if (!bagSave) { bagSave = { started: Number(r.fields.rosbag_saving_started_at), output: r.fields.rosbag_saving_output, last: null };
          $('bagsave-title').textContent = 'rosbag を保存中'; $('bagsave-bar').className = 'bagbar-run'; $('bagsave-ack').hidden = true; $('bagsave').hidden = false; updateBagSave(); }
      } else if (bagSave && !bagSave.finished) {
        let res = null; try { res = JSON.parse(r.fields.rosbag_last_save || 'null'); } catch (e) { res = null; }
        bagSave.finished = true;
        const ok = res && res.ok && res.output === bagSave.output;
        $('bagsave-title').textContent = ok ? 'rosbag の保存が完了' : 'rosbag の保存に失敗';
        $('bagsave-bar').className = 'bagbar-run ' + (ok ? 'done' : 'fail');
        $('bagsave-body').textContent = `${bagSave.output}\n${res ? `所要 ${fmtAge(res.finished_at - res.started_at)}、終了コード ${res.exit_code}` : ''}${ok ? '' : `\n${r.fields.last_failure || ''}`}`;
        $('bagsave-ack').hidden = false;
      }
    }
    // pop-up for a new recording failure (G-REC-ROSBAG-RESTART: a rosbag that ended without a stop request was silent).
    // The count received on (re)connect is the baseline and does not trigger it.
    const nFail = Number(r.fields.failures || 0);
    if (rf.status !== 'NOT_RECEIVED') {
      if (seenRecordFailures !== null && nFail > seenRecordFailures) {
        $('popup-title').textContent = '記録に失敗';
        $('popup-body').textContent = `${r.fields.last_failure || ''}\n走行は止めない。rosbag が必要なら Rosbag record ボタンで記録し直す（新しいフォルダに書く）。`;
        $('popup').hidden = false;
      }
      seenRecordFailures = nFail;
    }
    renderUsb(s);
    // esp32 (nothing until stage 5-5)
    const e = s.esp32;
    $('esp32-status').textContent = e.freshness.status; $('esp32-status').className = 'status ' + statusClass(e.freshness);
    kvTable($('esp32-table'), Object.keys(e.fields).length ? e.fields : {});
    $('esp32-note').textContent = e.note || e.freshness.verdict;
    // sensors (IFD-21 / IFD-22 / IFD-47 reception, DEC-088). Display only; the thresholds are PRM-57 / PRM-58 (GNSS has none).
    if (s.sensors) {
      const rows = {}; let allOk = true;
      for (const st of Object.values(s.sensors)) {
        if (st.status !== 'RECEIVED') allOk = false;
        rows[`${st.label} (${st.topic})`] = `${st.status}  ${st.rate_hz == null ? '— Hz' : st.rate_hz.toFixed(1) + ' Hz'}  age ${st.age_s == null ? '—' : st.age_s.toFixed(2) + ' s'}` +
          (st.stamp_minus_receive_s == null ? '' : `  stamp-受信 ${st.stamp_minus_receive_s.toFixed(3)} s`) + (st.stale_after_s == null ? '  (しきい値未確定: STALE 判定なし)' : '') +
          (st.detail ? `  ${st.detail}` : '');
      }
      kvTable($('sensors-table'), rows);
      $('sensors-status').textContent = allOk ? 'RECEIVED' : 'CHECK'; $('sensors-status').className = 'status ' + (allOk ? 'ok' : 'amber');
    }
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
    // map database (IFD-29) and the 地図 tab
    renderMaps(s);
    // settings (UI parameters of the relay node)
    if (s.settings && s.settings.ui) kvTable($('settings-table'), Object.assign({}, s.settings.ui, { declared_by: s.settings.declared_by, source: s.settings.source, auto_retry: s.settings.auto_retry }));
    // pop-ups for events that need the human's attention: a failed automatic log start (DEC-071) and GLIM ending during
    // mapping (G-GLIM-EXIT, TR-14 detection only). Only events newer than the last seen one trigger them; a retained
    // message received on (re)connect is not a trigger (DEC-072).
    const POPUP_EVENTS = {
      record_auto_start_failed: ['記録の自動開始に失敗', '走行は止めない。記録が必要なら Record ボタンで手動開始する。'],
      record_auto_stop_failed: ['記録の自動開始に失敗', '走行は止めない。記録が必要なら Record ボタンで手動開始する。'],   // text as before this change
      glim_exited: ['GLIM が停止した（地図作成中）', '地図は作られていない。地図作成終了ボタンを押して終える（自動での再起動はしない）。glim.log を確認する。'] };
    const failed = s.events.filter((ev) => ev.event in POPUP_EVENTS);
    const newest = failed.reduce((m, ev) => Math.max(m, ev.last_at), 0);
    if (seenEventsBaseline !== null && newest > seenEventsBaseline) {
      const ev = failed.find((x) => x.last_at === newest);
      const [title, advice] = POPUP_EVENTS[ev.event];
      $('popup-title').textContent = title;
      $('popup-body').textContent = `${fmtT(ev.last_at)} ${ev.transition_id || ''} ${ev.reason}\n${advice}`;
      $('popup').hidden = false;
    }
    if (seenEventsBaseline === null || newest > seenEventsBaseline) seenEventsBaseline = newest;
    $('clock').textContent = 'server ' + fmtT(s.now);
  }
  let seenEventsBaseline = null;   // set from the first snapshot after connect: retained history is not a trigger
  // ESP32 USB link (DEC-177): always on screen, never a pop-up (the vehicle PC screen is hard to operate)
  const fmtClock = (t) => (t ? new Date(Number(t) * 1000).toLocaleTimeString() : '—');
  function usbText(u, nowS) {
    if (!u || !u.link) return ['—', ''];
    const inSession = !!u.session, n = inSession ? `　切断 ${u.disconnects} 回` : '';
    if (u.link === 'down') return [`切断中 ${inSession && u.down_since ? fmtAge(nowS - Number(u.down_since)) : ''}${n}`, 'red'];
    if (u.link === 'not_open') return [`未接続${n}`, 'amber'];
    return [`OK${n}`, Number(u.disconnects || 0) > 0 ? 'amber' : 'cyan'];
  }
  function renderUsb(s) {
    const u = s.usb_link || {};
    const [t, c] = usbText(u, Date.now() / 1000); $('usb-short').textContent = t; $('usb-short').className = 'v ' + c;
    let last = {}; try { last = JSON.parse(u.last_session || 'null') || {}; } catch (e) { last = {}; }
    const kind = { mapping: '事前地図作成', autonomy: '自律走行' };
    kvTable($('usb-table'), u.link ? {
      'USB 接続': { up: '接続中', down: '切断中', not_open: '未接続（vehicle_bridge が開いていない）' }[u.link] || u.link,
      'セッション': u.session ? `${kind[u.session] || u.session}（${fmtClock(u.session_started_at)} から）` : 'なし（数えない）',
      '切断／再接続': u.session ? `${u.disconnects} 回 / ${u.reconnects} 回` : '—',
      '最後の切断／復帰': u.session ? `${fmtClock(u.last_down_at)} / ${fmtClock(u.last_up_at)}` : '—',
      '切断の合計時間': u.session && u.down_total_s !== '' ? fmtAge(Number(u.down_total_s)) : '—',
      '前回のセッション': last.kind ? `${kind[last.kind] || last.kind}: 切断 ${last.disconnects} 回、合計 ${fmtAge(Number(last.down_total_s))}` : '—',
    } : {});
  }
  let bagSave = null;   // the rosbag save shown in the progress pop-up (DEC-174)
  function fmtBytes(n) { if (n == null) return '不明'; const u = ['B', 'KB', 'MB', 'GB']; let i = 0; while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; } return `${n.toFixed(i ? 1 : 0)} ${u[i]}`; }
  async function updateBagSave() {
    if (!bagSave || bagSave.finished) return;
    try {
      const j = await (await fetch('/api/rosbag_saving', { cache: 'no-store' })).json();
      if (!bagSave || bagSave.finished || !j.saving) return;
      const elapsed = j.now - bagSave.started;
      let rate = '';
      if (bagSave.last && j.bytes != null && bagSave.last.bytes != null && j.now > bagSave.last.now) rate = `、増え方 ${fmtBytes(Math.max(0, (j.bytes - bagSave.last.bytes) / (j.now - bagSave.last.now)))}/s`;
      bagSave.last = { bytes: j.bytes, now: j.now };
      $('bagsave-body').textContent = `${j.output}\n経過 ${fmtAge(elapsed)}、書き出したファイル ${fmtBytes(j.bytes)}${rate}\n全体の量は分からないため、バーは保存中であることだけを示す。時間の上限はない。`;
    } catch (e) { /* the next tick retries */ }
  }
  $('bagsave-ack').addEventListener('click', () => { $('bagsave').hidden = true; bagSave = null; });
  let seenRecordFailures = null;   // recorder failure count at the first snapshot after connect (baseline)
  $('popup-ack').addEventListener('click', () => { $('popup').hidden = true; });

  // ---- 地図 tab (intent.md:106): map list, conversion settings, re-conversion, preview ----
  const mapSel = { origin: null, rev: null, view: 'map.png', terrain: null };
  // what each preview shows (DEC-095 kinds; the terrain views are for checking only, DEC-097 A)
  const VIEW_NOTE = {
    'map.png': '2D 占有格子（Nav2 が使う地図）。白: 空き（地面を観測）、黒: 占有、灰: 未知。',
    'height.png': '3D 点群地図を上から見た図。セルごとの地面からの最も高い点（障害物の上限まで）。濃い緑: 地面だけ。',
    'slope.png': '地面の傾き（地面を推定する格子ごと）。表示のみで、走行には使わない。',
    'step.png': '上下左右の格子との地面の高さの差（段差。坂では 1 格子分の上りを含む）。表示のみで、走行には使わない。' };
  function showView() {
    for (const b of document.querySelectorAll('#prev-views .view')) b.classList.toggle('sel', b.dataset.view === mapSel.view);
    if (mapSel.rev == null) { $('prev-img').removeAttribute('src'); $('prev-legend').textContent = ''; return; }
    $('prev-img').src = `/api/map/${encodeURIComponent(mapSel.origin)}/${mapSel.rev}/${mapSel.view}?t=${Date.now()}`;
    const v = mapSel.terrain && mapSel.terrain.views ? mapSel.terrain.views[mapSel.view] : null;
    const unit = v ? ({ deg: '度' }[v.unit] || v.unit) : '';
    const scale = v ? ` 色: 緑 0 → 黄 → 赤 ${v.scale_max} ${unit}（${v.scale_from}）、紫: それを超える、灰: データなし。` : '';
    $('prev-legend').textContent = (VIEW_NOTE[mapSel.view] || '') + scale + (mapSel.view !== 'map.png' && !mapSel.terrain ? '（この rev には無い。以前の変換器で作った rev）' : '');
  }
  $('prev-views').addEventListener('click', (e) => { const b = e.target.closest('.view'); if (b) { mapSel.view = b.dataset.view; showView(); } });
  let mapSettings = [];
  function renderMaps(s) {
    if (!s.maps) return;
    const origins = (s.maps.origins || []).slice().reverse();   // newest first
    $('maps-note').textContent = s.maps.note || `${origins.length} 原図`;
    $('maps-table').innerHTML = origins.map((o) => {
      const revs = (o.converted || []).map((c) => `<span class="rev ${mapSel.origin === o.origin_id && mapSel.rev === c.revision ? 'sel' : ''}" data-origin="${esc(o.origin_id)}" data-rev="${c.revision}">rev ${c.revision}</span>`).join('') || '<span class="dim">変換後地図なし</span>';
      return `<div class="origin ${mapSel.origin === o.origin_id ? 'sel' : ''}" data-origin="${esc(o.origin_id)}"><div>${esc(o.origin_id)} <span class="dim">submaps ${o.submaps} / ${fmtT(o.created_at)} / ${String(o.source_hash).slice(0, 12)}…</span></div><div>${revs}</div></div>`;
    }).join('') || '<div class="dim">原図なし（地図作成を終了すると登録される）</div>';
    const c = s.map_conversion || {};
    const st = c.state || 'idle';
    $('conv-status').textContent = st === 'running' ? `変換中 ${c.stage || ''} ${c.progress != null ? Math.round(c.progress * 100) + '%' : ''}` : st === 'done' ? `完了 rev ${c.revision}` : st === 'failed' ? '失敗' : '—';
    $('conv-status').className = 'status ' + (st === 'failed' ? 'amber' : st === 'done' ? 'ok' : '');
    $('conv-run').disabled = st === 'running';
    if (c.message) $('conv-msg').textContent = `${c.origin_id}: ${c.message}`;
    if (st === 'done' && c.origin_id && lastShownConversion !== c.finished_at) {   // show the new revision right away
      lastShownConversion = c.finished_at; selectMap(c.origin_id, c.revision);
    }
  }
  let lastShownConversion = null;
  $('maps-table').addEventListener('click', (e) => {
    const r = e.target.closest('.rev'); const o = e.target.closest('.origin');
    if (r) selectMap(r.dataset.origin, Number(r.dataset.rev)); else if (o) selectMap(o.dataset.origin, null);
  });
  async function selectMap(origin, rev) {
    mapSel.origin = origin; mapSel.rev = rev;
    $('conv-target').textContent = `対象の原図: ${origin}`;
    if (lastState) renderMaps(lastState);
    mapSel.terrain = null;
    if (rev == null) { $('prev-title').textContent = '未選択'; showView(); kvTable($('prev-table'), {}); return; }
    $('prev-title').textContent = `${origin} rev ${rev}`;
    try { const t = await (await fetch(`/api/map/${encodeURIComponent(origin)}/${rev}/terrain.json`)).json(); mapSel.terrain = t.ok ? t.terrain : null; } catch (err) { mapSel.terrain = null; }
    showView();
    try {
      const j = await (await fetch(`/api/map/${encodeURIComponent(origin)}/${rev}/manifest.json`)).json();
      const m = j.manifest || {}; const st = m.stats || {}; const rows = {};
      for (const s of mapSettings.length ? mapSettings : Object.keys(m.settings || {}).map((k) => ({ key: k, label: k, unit: '' }))) rows[`${s.label} [${s.unit}]`] = (m.settings || {})[s.key];
      Object.assign(rows, { 'セル（占有／空き／未知）': `${st.occupied} / ${st.free} / ${st.unknown}`, '大きさ': `${st.width}×${st.height} cells, 解像度 ${st.resolution} m`,
        '点（全体／障害物／地面）': `${st.points_total} / ${st.points_obstacle} / ${st.points_ground}`,
        '点（帯の間／上限より上／地面が不明）': st.points_between == null ? '—' : `${st.points_between} / ${st.points_above} / ${st.points_no_ground}`,
        '地面の格子（点あり／地面／補った）': st.terrain ? `${st.terrain.ground_cells_observed} / ${st.terrain.ground_cells_ground_like} / ${st.terrain.ground_cells_filled}` : '—',
        '傾きの最大／段差の最大': st.terrain ? `${st.terrain.slope_max_deg == null ? '—' : st.terrain.slope_max_deg.toFixed(1) + ' 度'} / ${st.terrain.step_max_m == null ? '—' : st.terrain.step_max_m.toFixed(2) + ' m'}` : '—',
        'ファイル': (m.files || []).join(', '), 'submaps': st.submaps, '変換器': (m.converter || {}).version,
        '内容ハッシュ': String(m.content_hash || '').slice(0, 16) + '…', '作成': fmtT(m.created_at) });
      kvTable($('prev-table'), rows);
      // the settings of the selected revision become the starting point of the next try
      for (const [k, v] of Object.entries(m.settings || {})) { const el = $('conv-form').elements[k]; if (el) el.value = v; }
    } catch (err) { kvTable($('prev-table'), { error: String(err) }); }
  }
  async function loadMapSettings() {
    try {
      const j = await (await fetch('/api/map_settings')).json();
      mapSettings = j.settings || [];
      const form = $('conv-form'); const keep = {};
      for (const el of form.elements) keep[el.name] = el.value;
      form.innerHTML = mapSettings.map((s) => `<label>${esc(s.label)} <span class="dim">[${esc(s.unit)}] ${esc(s.prm)}</span><input name="${esc(s.key)}" value="${esc(keep[s.key] != null && keep[s.key] !== '' ? keep[s.key] : (s.default == null ? '' : s.default))}" placeholder="未設定"></label>`).join('');
      $('conv-note').textContent = j.note || '';
    } catch (err) { $('conv-note').textContent = 'settings: ' + err; }
  }
  $('conv-defaults').addEventListener('click', () => {
    for (const s of mapSettings) { const el = $('conv-form').elements[s.key]; if (el) el.value = s.default == null ? '' : s.default; }
  });
  $('conv-run').addEventListener('click', async () => {
    if (!mapSel.origin) { $('conv-msg').textContent = '原図を選んでから再変換する'; return; }
    const settings = {}; for (const el of $('conv-form').elements) settings[el.name] = el.value;
    $('conv-run').disabled = true;
    try {
      const j = await (await fetch('/api/map_reconvert', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ origin_id: mapSel.origin, settings }) })).json();
      $('conv-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message;
    } catch (err) { $('conv-msg').textContent = 'request failed: ' + err; } finally { if (lastState) renderMaps(lastState); }
  });

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
  // ---- /config sub-tabs (REV-118): the page keeps only which one is open; the values live on the server ----
  document.querySelectorAll('.subtab').forEach((b) => b.addEventListener('click', () => {
    document.querySelectorAll('.subtab').forEach((x) => x.classList.toggle('active', x === b));
    document.querySelectorAll('.subpane').forEach((p) => p.classList.toggle('active', p.dataset.subpane === b.dataset.subtab));
    if (b.dataset.subtab === 'motion') loadMotionComp(); else if (b.dataset.subtab === 'nav2') loadNav2(); else loadConfig();
  }));

  // ---- /config 自律走行の出力: dead-band compensation (IFD-52, DEC-181) ----
  const MC_LABELS = {
    forward_min: '前進 最低倒し量', forward_threshold: '前進 しきい値',
    reverse_min: '後退 最低倒し量', reverse_threshold: '後退 しきい値',
    turn_min: '旋回 最低倒し量', turn_threshold: '旋回 しきい値',
  };
  async function loadMotionComp() {
    const r = await fetch('/api/motion_compensation'); renderMotionComp(await r.json());
  }
  function renderMotionComp(c) {
    const dirs = ['forward', 'reverse', 'turn'].filter((d) => c.values[d + '_min'] !== 'UNKNOWN' && c.values[d + '_threshold'] !== 'UNKNOWN');
    const names = { forward: '前進', reverse: '後退', turn: '旋回' };
    $('mc-rev').textContent = `revision ${c.config_revision} / 補償する向き: ${dirs.length ? dirs.map((d) => names[d]).join('・') : 'なし'} / ${c.path}`;
    $('mc-form').innerHTML = Object.keys(c.values).map((k) => {
      const v = c.values[k]; const unknown = v === 'UNKNOWN';
      return `<label><span>${esc(MC_LABELS[k] || k)} <span class="dim">(${esc(k)})</span></span><input name="${esc(k)}" class="${unknown ? 'unknown' : ''}" value="${esc(v)}" placeholder="UNKNOWN"></label>`;
    }).join('');
  }
  $('mc-save').addEventListener('click', async () => {
    const data = {}; new FormData($('mc-form')).forEach((v, k) => { data[k] = v; });
    try {
      const r = await fetch('/api/motion_compensation', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const j = await r.json(); $('mc-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message; $('mc-msg').className = j.ok ? 'cyan' : 'amber';
      if (j.config) renderMotionComp(j.config);
    } catch (err) { $('mc-msg').textContent = 'request failed: ' + err; $('mc-msg').className = 'amber'; }
  });

  // ---- /config Nav2: the BT recovery count used from the next gouda.sh start (IFD-54, DEC-209) ----
  async function loadNav2() {
    const r = await fetch('/api/nav2_recovery'); renderNav2(await r.json());
  }
  function renderNav2(c) {
    const lim = c.limits && c.limits.recovery_number_of_retries;
    $('nav2-rev').textContent = `revision ${c.config_revision} / ${c.path}`;
    $('nav2-form').innerHTML = Object.keys(c.values).map((k) => {
      const v = c.values[k]; const unknown = v === 'UNKNOWN';
      return `<label><span>recovery の回数 <span class="dim">(${esc(k)}${lim ? `, ${lim[0]}〜${lim[1]}` : ', PRM-18 未確定のため保存できない'})</span></span><input name="${esc(k)}" class="${unknown ? 'unknown' : ''}" value="${esc(v)}" placeholder="UNKNOWN"></label>`;
    }).join('');
    const row = (k, v) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`;
    const nx = c.next_start, iu = c.in_use;
    $('nav2-table').innerHTML = row('PRM-18（既定）', c.prm18 ?? '未確定')
      + row('次の gouda.sh start で使う値', nx ? `${nx.value}（${nx.source}${nx.note ? ' / ' + nx.note : ''}）` : '—')
      + row('今の起動で使っている値', iu ? `${iu.value}（${iu.source}${iu.note ? ' / ' + iu.note : ''}）` : '不明（Nav2 が起動していない）');
  }
  $('nav2-save').addEventListener('click', async () => {
    const data = {}; new FormData($('nav2-form')).forEach((v, k) => { data[k] = v; });
    try {
      const r = await fetch('/api/nav2_recovery', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
      const j = await r.json(); $('nav2-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message; $('nav2-msg').className = j.ok ? 'cyan' : 'amber';
      if (j.config) renderNav2(j.config);
    } catch (err) { $('nav2-msg').textContent = 'request failed: ' + err; $('nav2-msg').className = 'amber'; }
  });

  $('config-save').addEventListener('click', async () => {
    const data = {}; new FormData($('config-form')).forEach((v, k) => { data[k] = v; });
    const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    const j = await r.json(); $('config-msg').textContent = (j.ok ? 'OK: ' : 'NG: ') + j.message; $('config-msg').className = j.ok ? 'cyan' : 'amber';
    if (j.config) renderConfig(j.config);
  });

  // ---- waypoint_manager (IFD-30 / IFD-41): edits on the converted map; save generates the speed mask ----
  const wpState = { map: null, geom: null, img: null, points: [], limits: [], scale: 1 };
  // ---- autonomy preparation (体験 9, IFD-02): the selected set (its map comes with it), the preview, the initial pose ----
  const autoState = { sel: null };
  function autoPose() {
    const x = parseFloat($('auto-x').value), y = parseFloat($('auto-y').value), yd = parseFloat($('auto-yaw-deg').value);
    return [x, y, yd].every((v) => Number.isFinite(v)) ? { x, y, yaw: yd * Math.PI / 180 } : null;
  }
  function autoStartBody() {
    const b = { request_id: 'ui-' + Date.now() };
    if (autoState.sel) Object.assign(b, autoState.sel);
    const p = autoPose(); if (p) b.initial_pose = p;   // without it the mode manager refuses the start (TR-05 guard)
    return b;
  }
  async function autoPreview() {
    const v = $('auto-set').value; if (!v) { $('auto-msg').textContent = '保存済みの waypoint セットがない'; return; }
    const [sid, rev] = v.split('/');
    const j = await (await fetch(`/api/route/${sid}/${rev}`)).json();
    if (!j.ok) { $('auto-msg').textContent = 'NG: ' + j.message; return; }
    const m = j.set.map;
    const g = await (await fetch(`/api/map/${m.origin_id}/${m.revision}/geometry.json`)).json();
    if (!g.ok) { $('auto-msg').textContent = 'NG: ' + g.message; return; }
    const img = new Image(); img.src = `/api/map/${m.origin_id}/${m.revision}/map.png?t=${Date.now()}`;
    img.onload = () => {
      wpState.map = { origin: m.origin_id, rev: m.revision, hash: m.content_hash }; wpState.geom = g; wpState.img = img;
      wpState.points = j.set.waypoints.map((w) => Object.assign({}, w)); wpState.limits = j.set.section_limits_mps.slice(); wpDraw();
      autoState.sel = { waypoint_set_id: sid, waypoint_set_revision: String(parseInt(rev, 10)), waypoint_set_hash: j.manifest.content_hash,
                        map_id: m.origin_id, map_revision: String(m.revision), map_hash: m.content_hash };
      $('auto-msg').textContent = `選択: ${sid}/${rev}（地図 ${m.origin_id}/${m.revision}、${j.set.waypoints.length} 点）。初期位置を入れてから「自律走行」を押す`;
    };
  }
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
      const as = $('auto-set'); const acur = as.value; as.innerHTML = '';
      (s.routes.sets || []).forEach((st) => st.revisions.forEach((r) => { const o = document.createElement('option'); o.value = `${st.set_id}/${r.revision}`; o.textContent = `${st.set_id} rev ${r.revision} (map ${r.map.origin_id}/${r.map.revision})`; as.appendChild(o); }));
      if (acur) as.value = acur;
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
    const ip = autoPose();
    if (ip) {   // the initial pose (an arrow in the heading)
      const [px, py] = toPx(ip); const L = 18;
      ctx.strokeStyle = '#ff5c8a'; ctx.lineWidth = 3; ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(px + L * Math.cos(ip.yaw), py - L * Math.sin(ip.yaw)); ctx.stroke();
      ctx.fillStyle = '#ff5c8a'; ctx.beginPath(); ctx.arc(px, py, 5, 0, Math.PI * 2); ctx.fill();
    }
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
    if ($('auto-click-pose').checked) {   // place the initial pose instead of a waypoint
      $('auto-x').value = Math.round(x * 1000) / 1000; $('auto-y').value = Math.round(y * 1000) / 1000;
      if ($('auto-yaw-deg').value === '') $('auto-yaw-deg').value = '0';
      wpDraw(); return;
    }
    wpState.points.push({ x: Math.round(x * 1000) / 1000, y: Math.round(y * 1000) / 1000, yaw: 0, kind: 'pass' });
    if (wpState.points.length > 1) wpState.limits.push(wpState.limits.length ? wpState.limits[wpState.limits.length - 1] : null);
    wpDraw();
  });
  $('wp-load-map').addEventListener('click', wpLoadMap);
  $('auto-preview').addEventListener('click', autoPreview);
  ['auto-x', 'auto-y', 'auto-yaw-deg'].forEach((id) => $(id).addEventListener('change', wpDraw));
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
  setInterval(() => { updateBagSave(); if (lastState) { const [t, c] = usbText(lastState.usb_link, Date.now() / 1000); $('usb-short').textContent = t; $('usb-short').className = 'v ' + c; }
    if (lastState) { const s = lastState; const dt = Date.now() / 1000 - s.now; if (s.mode.freshness.age_s != null) $('mode-age').textContent = fmtAge(s.mode.freshness.age_s + dt); } }, 1000);
})();
