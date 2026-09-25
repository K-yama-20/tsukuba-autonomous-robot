'use strict';
const $ = id => document.getElementById(id);
const titles = {
  mapping:['01 / MAPPING','地図をつくる','LiDARの観測を地図に重ね、保存します。'],
  planning:['02 / PLANNING','走行ルートを決める','位置を指定し、走行前に経路を確認します。'],
  monitor:['03 / MONITOR','走行を見守る','現在位置と予定経路、車体の状態を確認します。'],
  diagnostics:['04 / SYSTEM','状態を確認する','センサー、座標、制御系の更新状況を確認します。'],
  recording:['05 / RECORD','センサーを記録する','生データの保存と、次回のSLAM方式を設定します。'],
  autonomy:['06 / OPT-IN','自動運転 MVP','明示起動、未校正条件、センサーと運転状態を確認します。']
};
const names = {IDLE:'待機中',PLANNING:'経路計算中',PREVIEW_READY:'経路確認待ち',TRACKING:'走行中',ALIGNING:'向きを調整中',REACHED:'到着',CANCELLED:'中止',PREVIEW_EXPIRED:'経路の再計算が必要',PREVIEW_STALE:'開始位置が変わりました',SENSOR_OR_TF_FAULT:'入力異常で停止',PLAN_FAILED:'経路が見つかりません',PLAN_UNAVAILABLE:'経路計算の準備待ち',NO_PROGRESS:'進行停止を検出'};
let state=null, token=null, busy=false, connected=false, lastResponse=0, tab='mapping', view='2d', tool='pan', dirty=false, lastGoalKey='';
let camera={x:0,y:0,scale:35}, cameraInitialized=false, draft=null, pointer=null, mapCache=null, mapRevision=-1, mapListKey='';
const canvas=$('map'), ctx=canvas.getContext('2d');
function notice(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}
function selectTab(next){
  tab=next;document.body.dataset.tab=next;
  if(next==='planning')view='2d';
  for(const button of document.querySelectorAll('[data-tab]')){
    const selected=button.dataset.tab===next;button.setAttribute('aria-selected',String(selected));
    $('panel-'+button.dataset.tab).hidden=!selected;
  }
  const t=titles[next];$('eyebrow').textContent=t[0];$('page-title').textContent=t[1];$('page-description').textContent=t[2];
  if(next!=='planning')setTool('pan');
  try{localStorage.setItem('gouda-tab',next);}catch{}
  draw();
}
for(const b of document.querySelectorAll('[data-tab]')){
  b.addEventListener('click',()=>selectTab(b.dataset.tab));
  b.addEventListener('keydown',e=>{if(!['ArrowDown','ArrowUp','Home','End'].includes(e.key))return;e.preventDefault();const tabs=[...document.querySelectorAll('[data-tab]')];let i=tabs.indexOf(b);i=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowDown'?1:tabs.length-1))%tabs.length;tabs[i].focus();selectTab(tabs[i].dataset.tab);});
}
try{const remembered=localStorage.getItem('gouda-tab');if(titles[remembered])selectTab(remembered);}catch{}
async function request(action,data={},timeoutMs=25000){
  if(!token)throw new Error('Ubuntuへの接続を確認してください');
  const response=await fetch('/api/'+action,{method:'POST',headers:{'Content-Type':'application/json','X-Gouda-Session':token},body:JSON.stringify(data),signal:AbortSignal.timeout(timeoutMs)});
  const body=await response.json();if(!response.ok||body.ok===false)throw new Error(body.error||body.message||'操作できませんでした');return body;
}
async function act(action,data={},success='操作を受け付けました。',timeoutMs=25000){
  if(busy&&action!=='stop')return false;
  const normal=action!=='stop';if(normal)busy=true;render();
  try{await request(action,data,timeoutMs);notice(success);return true;}
  catch(error){notice(error.name==='TimeoutError'?'応答待ちがタイムアウトしました。状態を確認してください。':error.message,true);return false;}
  finally{if(normal)busy=false;render();}
}
async function poll(){
  try{
    if(!token){const session=await fetch('/api/session',{signal:AbortSignal.timeout(2500)});if(!session.ok)throw new Error('Session');token=(await session.json()).token;}
    const response=await fetch('/api/state',{signal:AbortSignal.timeout(2500)});if(!response.ok)throw new Error('State');
    state=await response.json();lastResponse=performance.now();
    updateRecordingSettings(); updateMappingSettings(); updateAutonomy();
    const selectedPose=tool==='start'?state.planning_start:tool==='goal'?state.goal:null;
    const selectedKey=JSON.stringify({tool,pose:selectedPose});
    if(selectedPose&&selectedKey!==lastGoalKey&&!dirty){writePose(selectedPose);lastGoalKey=selectedKey;}
    if(!connected)notice('Ubuntuに接続しました。状態を受信しています。');connected=true;
    if(state.map&&state.map_revision!==mapRevision){buildMap();if(!cameraInitialized)cameraInitialized=fit();}
    updateSavedMaps();render();draw();
  }catch{connected=false;token=null;render();draw();}
  setTimeout(poll,500);
}
function fresh(key,limit=.7){return connected&&state?.ages[key]!==undefined&&state.ages[key]+(performance.now()-lastResponse)/1000<limit;}
function setTool(next){
  tool=next;
  if(!dirty&&state){const pose=next==='start'?state.planning_start:next==='goal'?state.goal:null;if(pose)writePose(pose);}
  $('tool-start').setAttribute('aria-pressed',String(next==='start'));$('tool-goal').setAttribute('aria-pressed',String(next==='goal'));$('tool-initial').setAttribute('aria-pressed',String(next==='initial'));
  $('apply-pose').textContent=next==='initial'?'自己位置の初期設定を送信':next==='start'?'計画開始位置を設定':'入力値をゴールに設定';
  $('pose-help').textContent=next==='initial'?(state?.observation_only?'保存したSLAM地図でLiDAR位置推定を開始し、指定位置を初期値として送信します。':'自己位置推定へ指定位置を送信します。'):next==='start'?'経路計算だけに使う開始位置です。実測位置や自己位置推定は変更しません。':'位置はクリック、向きはドラッグで指定できます。';
  $('tool-hint').textContent=next==='pan'?'ドラッグで移動 · ホイールで拡大':next==='goal'?'クリックでゴール · ドラッグで向き':next==='start'?'クリックで計画開始位置 · ドラッグで向き':'位置と向きを指定後、右側で適用';
  if(next!=='pan'&&view!=='2d')setView('2d');
  render();
}
function poseFields(){
  const values=['pose-x','pose-y','pose-yaw'].map(id=>$(id).value.trim());
  if(values.some(v=>!v||!Number.isFinite(Number(v))))throw new Error('位置と向きを数値で入力してください');
  return {x:Number(values[0]),y:Number(values[1]),yaw:Number(values[2])*Math.PI/180};
}
function writePose(p){$('pose-x').value=p.x.toFixed(2);$('pose-y').value=p.y.toFixed(2);$('pose-yaw').value=(p.yaw*180/Math.PI).toFixed(0);}
for(const id of ['pose-x','pose-y','pose-yaw'])$(id).addEventListener('input',()=>{dirty=true;try{draft=poseFields();}catch{draft=null;}render();draw();});
async function applyPose(){
  try{const p=poseFields(),kind=tool==='initial'?'initial_pose':tool==='start'&&state?.observation_only?'planning_start':'target';
    if(await act(kind,p,kind==='target'?'ゴールを設定しました。経路を計算してください。':kind==='planning_start'?'計画開始位置を設定しました。実測位置は変更していません。':'初期位置を送信しました。現在位置の反映を確認してください。')){dirty=false;draft=null;}
  }catch(e){notice(e.message,true);}render();draw();
}
$('apply-pose').onclick=applyPose;
$('tool-start').onclick=()=>setTool(tool==='start'?'pan':'start');$('tool-goal').onclick=()=>setTool(tool==='goal'?'pan':'goal');$('tool-initial').onclick=()=>setTool(tool==='initial'?'pan':'initial');
$('mapping-start').onclick=()=>act('mapping_start',{},'地図作成を開始しました。');
$('mapping-stop').onclick=()=>act('mapping_stop',{},'地図作成を終了しました。名前を付けて保存してください。');
$('save-map').onclick=()=>act('save_map',{name:$('map-title').value},'地図を保存しました。');
$('load-map').onclick=()=>loadMap($('map-select').value);
async function loadMap(id){if(!id){notice('保存地図を選択してください。',true);return;}if(await act('load_map',{id},'地図を読み込みました。')){dirty=false;draft=null;cameraInitialized=false;for(const field of ['pose-x','pose-y','pose-yaw'])$(field).value='';}}
$('plan').onclick=async()=>{if(dirty){notice('変更した位置を先に適用してください。',true);return;}await act('plan',{},state?.observation_only?'経路プレビューを計算しました。走行は開始していません。':'経路計算中です。走行は開始していません。',50000);};
$('to-monitor').onclick=()=>selectTab('monitor');
$('start').onclick=()=>act('start',{plan_id:state?.plan_id},'走行開始を受け付けました。');
$('stop').onclick=$('cancel').onclick=()=>act('stop',{},'停止要求を送信しました。停止確認を待っています。');

let recordingConfigLoaded=false,mappingConfigLoaded=false,autonomyConfigLoaded=false,autonomyPortsKey='';
function updateRecordingSettings(){
  const c=state?.recording_config;if(c&&!recordingConfigLoaded){const topics=new Set([...(c.topics||[]),...(state?.recording?.config?.topics||[])]);$('rec-lidar').checked=topics.has('/lidar_points');$('rec-imu').checked=topics.has('/imu/data_raw');$('rec-kiss-odom').checked=topics.has('/kiss/odometry');$('rec-glim-odom').checked=true;$('rec-cmd-vel').checked=true;$('rec-clock').checked=topics.has('/clock')||state.mode==='replay';$('rec-storage').value=c.storage_id||'mcap';$('rec-duration').value=Math.round(c.max_duration_sec/60);$('rec-size').value=Math.round(c.max_bag_size_mb/1024);$('rec-disk').value=Math.round(c.min_free_disk_mb/1024);recordingConfigLoaded=true;}
  $('rec-clock').disabled=state.mode==='replay';if(state.mode==='replay')$('rec-clock').checked=true;
  const r=state?.recording||{};const labels={idle:'待機中',awaiting_sensor_data:'センサー入力待ち',recording:'記録中',finalizing:'ファイル確定中',no_sensor_data:'記録データなし',completed:'記録完了',failed:'記録エラー'};
  $('recording-phase').textContent=labels[r.phase]||'状態不明';$('recording-time').textContent=`${Math.floor((r.elapsed_sec||0)/60).toString().padStart(2,'0')}:${Math.floor((r.elapsed_sec||0)%60).toString().padStart(2,'0')}`;
  $('recording-size').textContent=r.directory?`bags/recordings/${r.directory.split('/').pop()}${Number.isFinite(r.bag_size_bytes)?' · '+(r.bag_size_bytes/1073741824).toFixed(2)+' GB':''}`:'保存先未作成';
  $('recording-message').textContent=r.error||(!r.sensor_data_seen&&['completed','no_sensor_data'].includes(r.phase)?'センサーの記録データを確認できません。成功した記録として扱っていません。':r.phase==='finalizing'?'記録ファイルとメタデータを確定しています。完了までお待ちください。':r.phase==='recording'?'センサー入力を観測しました（暫定）。終了後に記録件数とファイルを照合します。':r.phase==='awaiting_sensor_data'?'入力データが届くまで記録結果は確定しません。':r.phase==='completed'&&!r.metadata_verified?'バッグのメタデータを確認できません。記録結果は未検証です。':r.phase==='completed'?`記録とメタデータを確認しました。全トピックのメッセージ件数: ${Object.values(r.per_topic_counts||{}).reduce((a,b)=>a+b,0)}`:'設定保存は記録状態を変更しません。');
  updateRecordingCoverage(r);
  const running=['awaiting_sensor_data','recording','finalizing','no_sensor_data'].includes(r.phase);$('recording-start').disabled=busy||!connected||running;$('recording-stop').disabled=busy||!connected||!running;
}
function updateMappingSettings(){
  const m=state?.mapping_settings;if(!m)return;
  if(!mappingConfigLoaded){const c=m.saved||{};$('mapping-backend').value=c.backend||'kiss_icp';$('mapping-compute').value=c.compute||'cpu';$('map-tx').value='';$('map-ty').value='';$('map-tz').value='';if(c.extrinsic_lidar_imu?.translation_m){$('map-tx').value=c.extrinsic_lidar_imu.translation_m[0];$('map-ty').value=c.extrinsic_lidar_imu.translation_m[1];$('map-tz').value=c.extrinsic_lidar_imu.translation_m[2];}$('map-quat').value=c.extrinsic_lidar_imu?.quaternion_xyzw?.join(',')||'';$('map-point-time').value=c.point_time_unit||'unknown';$('map-accel-unit').value=c.imu_accel_unit||'unknown';$('map-gyro-unit').value=c.imu_gyro_unit||'unknown';$('map-point-mode').value=c.point_time_mode||'unknown';$('map-point-field').value=c.point_time_field||'unknown';$('map-point-type').value=c.point_time_datatype||'unknown';$('map-lidar-offset').value=c.lidar_clock_offset_sec??'';$('map-imu-offset').value=c.imu_clock_offset_sec??'';$('map-clock-policy').value=['host_mapped','external_common'].includes(c.clock_policy)?c.clock_policy:'unknown';$('map-clock-evidence').value=c.clock_evidence||'';mappingConfigLoaded=true;}
  const glim=$('mapping-backend').value==='glim_imu';$('mapping-calibration').hidden=!glim;
  const sync=state.time_sync||{status:'unverified',fresh:false,age_sec:null,errors:['状態トピック未受信']};const syncErrors=Array.isArray(sync.errors)?sync.errors:[];const syncAge=Number.isFinite(sync.age_sec)?`${sync.age_sec.toFixed(1)}秒前`:'受信時刻なし';const syncBlocked=sync.fresh!==true||syncErrors.length>0||['error','failed','fault','blocked','stale','unsynchronized'].includes(String(sync.status||'').toLowerCase());$('time-sync-state').dataset.syncState=syncBlocked?'blocked':'unverified';$('time-sync-state').textContent=`${syncBlocked?'状態停止（ブロック）':'状態更新中（同期精度は未検証）'} · ${sync.status||'unknown'} · ${syncAge}${syncErrors.length?' · '+syncErrors.join(' / '):''}`;
  const active=m.active||{};const readyLabel=m.saved?.backend==='glim_imu'?(m.ready?'GLIM入力設定確認済み':'GLIM入力設定未準備'):'GLIM入力設定は未選択';
  $('mapping-settings-state').textContent=`保存設定: ${m.saved?.backend||'不明'} / ${readyLabel} · 起動時の動作方式: ${active.backend||'未起動'}${active.compute?' / '+active.compute:''}${active.state?' · '+active.state:''}${m.package_available===true?' · GLIMパッケージ利用可':m.package_available===false?' · GLIMパッケージ利用不可':''}${m.runtime_available===true?' · GLIM処理実行中':m.runtime_available===false?' · GLIM処理停止中':''}${active.input_state?` · 入力 LiDAR:${active.input_state.lidar} IMU:${active.input_state.imu} odom:${active.input_state.odometry}`:''}${active.error?' · '+active.error:''}${active.output_directory?' · 3D記録 '+active.output_directory:''}${m.restart_required?' · 保存設定の適用にはMission Control再起動が必要':''}`;
}
const CONTROL_ANALYSIS_TOPICS=['/cmd_motion','/gouda/motion_permit','/esp32/status','/gouda/navigation_state','/gouda/pose','/glim_ros/lidar_odom','/cmd_vel'];
function updateRecordingCoverage(r){
  const counts=r.per_topic_counts||{},lidar=Number(counts['/lidar_points']||0),imu=Number(counts['/imu/data_raw']||0),terminal=['completed','failed'].includes(r.phase);
  $('recording-raw-coverage').textContent=r.metadata_verified?`生センサー: 検証済み · LiDAR ${lidar}件 / IMU ${imu}件`:terminal?`生センサー: 未検証 · LiDAR ${lidar}件 / IMU ${imu}件`:(r.sensor_data_seen?`生センサー: 入力を観測（暫定） · LiDAR ${lidar}件 / IMU ${imu}件`:'生センサー: 入力待ち · LiDAR・IMUの両方の記録を終了後に照合');
  const topics=CONTROL_ANALYSIS_TOPICS,observed=topics.filter(topic=>Number(counts[topic]||0)>0),missing=Array.isArray(r.missing_control_topics)?r.missing_control_topics.filter(topic=>topics.includes(topic)):null;
  const detail=terminal?(missing===null?'記録件数を照合できません':`未取得: ${missing.length?missing.join('、'):'なし'}`):r.control_data_seen?'制御関連入力を観測（暫定）':'制御関連入力を待っています';
  $('recording-control-coverage').textContent=`操作・推定データ: ${observed.length}/${topics.length}項目に記録あり · ${detail}`;
}
function recordingTopics(){
  const topics=['/lidar_points','/imu/data_raw','/tf','/tf_static',...CONTROL_ANALYSIS_TOPICS];
  if($('rec-kiss-odom').checked)topics.push('/kiss/odometry');
  if($('rec-clock').checked||state?.mode==='replay')topics.push('/clock');
  const sources=[state?.recording_config?.topics||[],state?.recording?.config?.topics||[]];
  const managed=new Set([...topics,'/kiss/odometry','/clock']);
  for(const source of sources)for(const topic of source)if(!managed.has(topic)&&!topics.includes(topic))topics.push(topic);
  return [...new Set(topics)];
}
$('recording-save').onclick=()=>act('recording_config_save',{topics:recordingTopics(),storage_id:$('rec-storage').value,max_duration_sec:Number($('rec-duration').value)*60,max_bag_size_mb:Number($('rec-size').value)*1024,min_free_disk_mb:Number($('rec-disk').value)*1024},'記録設定を保存しました。現在の記録状態は変わりません。');
$('recording-start').onclick=()=>act('recording_start',{},'記録要求を受け付けました。センサー入力と保存状態を確認しています。');
$('recording-stop').onclick=()=>act('recording_stop',{},'記録終了処理を開始しました。完了状態を確認してください。');
const autonomyPhases={idle:'待機中',arming:'開始確認中',blocked:'障害物で停止中',running:'自動走行中',paused_manual:'手動操作を優先中（目標は保持）',blocked_sensor:'センサー入力待ち',blocked_calibration:'校正待ち',blocked_obstacle:'障害物で停止中',completed:'目標に到達',cancelled:'中止',fault:'異常停止'};
function updateAutonomy(){
  const a=state?.autonomy;if(!a)return;
  const settings=a.settings||{},saved=settings.saved||{},ports=settings.serial_ports||[];
  const portsKey=JSON.stringify(ports);
  if(portsKey!==autonomyPortsKey){const select=$('autonomy-serial-port'),selected=select.value;select.replaceChildren(new Option('未選択',''));for(const port of ports)select.add(new Option(port,port));autonomyPortsKey=portsKey;if(ports.includes(selected))select.value=selected;}
  if(!autonomyConfigLoaded&&settings.saved){
    $('autonomy-hardware-enabled').checked=saved.hardware_enabled===true;
    if(saved.serial_port&&ports.includes(saved.serial_port))$('autonomy-serial-port').value=saved.serial_port;
    const t=saved.body_to_lidar?.translation_m,q=saved.body_to_lidar?.quaternion_xyzw;
    if(Array.isArray(t)&&t.length===3){$('autonomy-tx').value=t[0];$('autonomy-ty').value=t[1];$('autonomy-tz').value=t[2];}
    if(Array.isArray(q)&&q.length===4)$('autonomy-quat').value=q.join(',');
    autonomyConfigLoaded=true;
  }
  const runtime=a.state||{},active=['arming','running','paused_manual','blocked'].includes(runtime.phase);
  const phase=runtime.phase||(!a.profile_enabled?'プロフィール未起動':'状態待ち');
  $('autonomy-phase').textContent=autonomyPhases[phase]||phase;
  const ref=runtime.command_ref||{},estimate=runtime.estimate||{};
  const dataParts=[];
  if(runtime.manual_override===true)dataParts.push('手動入力を優先中');
  if(typeof runtime.reason==='string'&&runtime.reason)dataParts.push(runtime.reason);
  if(runtime.pose_fresh===true)dataParts.push('位置推定: 更新中');else if(runtime.pose_fresh===false)dataParts.push('位置推定: 停止/未受信');
  if(runtime.imu_fresh===true)dataParts.push('IMU: 更新中');else if(runtime.imu_fresh===false)dataParts.push('IMU: 停止/未受信');
  if(runtime.command_ref&&Number.isFinite(ref.v_mps)&&Number.isFinite(ref.w_rps))dataParts.push(`要求値 ${ref.v_mps.toFixed(2)} m/s · ${ref.w_rps.toFixed(2)} rad/s`);
  if(runtime.estimate&&Number.isFinite(estimate.v_mps))dataParts.push(`推定 ${estimate.v_mps.toFixed(2)} m/s`);
  $('autonomy-detail').textContent=dataParts.join(' · ')|| (a.state_fresh?'状態を受信しています':'自動制御ノードの状態を待っています');
  const reasons=[];
  if(!a.profile_enabled)reasons.push('この画面だけでは自動制御を開始できません。設定後に gouda.sh autonomy で明示起動してください。');
  if(settings.restart_required)reasons.push('保存設定の適用には自動運転プロファイルの再起動が必要です。');
  if(!settings.ready)reasons.push(...(settings.errors||['シリアル接続または取付設定が未準備です。']));
  if(!a.state_fresh)reasons.push('PC自動制御状態が未受信または古くなっています。');
  if(a.state_fresh&&runtime.pose_fresh!==true)reasons.push('位置推定が新しく届いていません。');
  if(a.state_fresh&&runtime.imu_fresh!==true)reasons.push('IMU入力が新しく届いていません。');
  if(a.state_fresh&&runtime.calibration_ready!==true)reasons.push(runtime.reason||'LiDAR・IMU・車体の取付変換または制御校正が未確認です。');
  if(runtime.manual_override===true)reasons.push('手動操作が優先です。手動入力が中立になり、PC状態が更新されるまで開始できません。');
  if(active)reasons.push(runtime.reason||'自動制御が進行中です。');
  const inputs=['autonomy-forward','autonomy-left','autonomy-heading','autonomy-target-v','autonomy-target-w'].map(id=>$(id).value.trim());
  const nums=inputs.map(Number),targetsValid=inputs.every(v=>v!=='')&&nums.every(Number.isFinite)&&nums[3]>0&&nums[4]>0;
  if(!targetsValid)reasons.push('前進速度と旋回速度を0より大きい数値で入力してください。');
  $('autonomy-readiness').textContent=reasons.length?reasons.join(' '):'準備完了。開始操作で記録を起動・確認し、PCに一度だけ開始要求を送ります。';
  const startReady=a.profile_enabled&&settings.ready&&!settings.restart_required&&a.state_fresh&&runtime.pose_fresh===true&&runtime.imu_fresh===true&&runtime.calibration_ready===true&&runtime.manual_override!==true&&!active&&['idle','cancelled','completed','fault'].includes(runtime.phase)&&targetsValid;
  $('autonomy-start').disabled=busy||!connected||!startReady;
  $('autonomy-cancel').disabled=busy||!a.profile_enabled||!a.state||['idle','completed','cancelled'].includes(runtime.phase);
  $('autonomy-settings-save').disabled=busy||!connected||['arming','running','paused_manual','blocked'].includes(runtime.phase);
  $('autonomy-hardware-enabled').disabled=busy||!connected;
  $('autonomy-serial-port').disabled=busy||!connected;
  for(const id of ['autonomy-tx','autonomy-ty','autonomy-tz','autonomy-quat'])$(id).disabled=busy||!connected;
}
function autonomySettingsFromForm(){
  const current=state?.autonomy?.settings?.saved;if(!current)throw new Error('自動運転設定を読み込めません');
  const raw=['autonomy-tx','autonomy-ty','autonomy-tz'].map(id=>$(id).value.trim()),q=$('autonomy-quat').value.split(',').map(v=>Number(v.trim()));
  let bodyToLidar=null;
  if(raw.some(v=>v!=='')){
    const t=raw.map(Number);
    if(raw.some(v=>v==='')||t.some(v=>!Number.isFinite(v))||q.length!==4||q.some(v=>!Number.isFinite(v)))throw new Error('T_body_lidarは位置3値とquaternion 4値をすべて入力してください');
    bodyToLidar={translation_m:t,quaternion_xyzw:q};
  }else if($('autonomy-quat').value.trim()!=='')throw new Error('T_body_lidarの位置と回転をそろえて入力してください');
  return {...current,hardware_enabled:$('autonomy-hardware-enabled').checked,serial_port:$('autonomy-serial-port').value||null,body_to_lidar:bodyToLidar};
}
$('autonomy-settings-save').onclick=async()=>{try{await act('autonomy_settings_save',autonomySettingsFromForm(),'設定を保存しました。シリアル接続は次回の明示起動時に行います。');autonomyConfigLoaded=false;}catch(error){notice(error.message,true);}};
$('autonomy-start').onclick=()=>{
  const vals=['autonomy-forward','autonomy-left','autonomy-heading','autonomy-target-v','autonomy-target-w'].map(id=>Number($(id).value));
  act('autonomy_start',{goal:{forward_m:vals[0],left_m:vals[1],yaw_rad:vals[2]*Math.PI/180},target_v_mps:vals[3],target_w_rps:vals[4]},'開始要求を送りました。PC自動制御状態を確認しています。');
};
$('autonomy-cancel').onclick=()=>act('autonomy_cancel',{},'中止要求を送りました。PC状態の更新を確認してください。');
for(const id of ['autonomy-forward','autonomy-left','autonomy-heading','autonomy-target-v','autonomy-target-w'])$(id).addEventListener('input',updateAutonomy);

$('mapping-backend').onchange=()=>{$('mapping-calibration').hidden=$('mapping-backend').value!=='glim_imu';};
$('mapping-settings-save').onclick=()=>{
  let translation=[['map-tx','map-ty','map-tz'].map(id=>$(id).value.trim())];
  const vals=translation[0].map(Number),q=$('map-quat').value.split(',').map(v=>Number(v.trim()));
  let ext=null;if(translation[0].every(v=>v!=='')){if(vals.some(v=>!Number.isFinite(v))||q.length!==4||q.some(v=>!Number.isFinite(v)))return notice('取付変換は位置3値と回転4値を入力してください。',true);ext={translation_m:vals,quaternion_xyzw:q};}
  let lidarOffset=$('map-lidar-offset').value.trim(),imuOffset=$('map-imu-offset').value.trim();const config={backend:$('mapping-backend').value,compute:$('mapping-compute').value,lidar_topic:'/lidar_points',imu_topic:'/imu/data_raw',lidar_frame:'hesai_lidar',imu_frame:'imu_link',extrinsic_lidar_imu:ext,point_time_mode:$('map-point-mode').value,point_time_field:$('map-point-field').value,point_time_datatype:$('map-point-type').value,point_time_unit:$('map-point-time').value,clock_policy:$('map-clock-policy').value,clock_evidence:$('map-clock-evidence').value.trim(),imu_accel_unit:$('map-accel-unit').value,imu_gyro_unit:$('map-gyro-unit').value,lidar_clock_offset_sec:lidarOffset===''?null:Number(lidarOffset),imu_clock_offset_sec:imuOffset===''?null:Number(imuOffset)};
  if([lidarOffset,imuOffset].some(v=>v!==''&&!Number.isFinite(Number(v))))return notice('センサー時刻補正を数値で入力してください。',true);
  act('mapping_settings_save',config,'SLAM設定を保存しました。動作中の方式は切り替わっていません。');
};

$('map-title').addEventListener('input',render);
function setView(next){view='2d';$('view-label').textContent='2D 地図 / map座標系';draw();}
$('fit').onclick=()=>{fit();draw();};
function updateSavedMaps(){
  const list=state.maps||[],key=JSON.stringify(list);if(key===mapListKey)return;mapListKey=key;
  const selected=$('map-select').value;$('map-select').replaceChildren(new Option('保存地図を選択',''));$('saved-maps').replaceChildren();
  if(!list.length){const p=document.createElement('p');p.className='helper';p.textContent='保存済み地図はありません。';$('saved-maps').append(p);}
  for(const m of list){$('map-select').add(new Option(m.name,m.id));const row=document.createElement('div');row.className='saved-map';const text=document.createElement('div'),name=document.createElement('strong'),date=document.createElement('small');name.textContent=m.name;date.textContent=new Date(m.created*1000).toLocaleString('ja-JP',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})+' · '+(m.mode==='simulation'?'模擬':m.mode==='replay'?'記録再生':'実機');text.append(name,date);const b=document.createElement('button');b.textContent='開く';b.addEventListener('click',()=>loadMap(m.id));row.append(text,b);$('saved-maps').append(row);}
  if(list.some(m=>m.id===selected))$('map-select').value=selected;
}
function render(){
  document.body.classList.toggle('disconnected',!connected);
  $('connection').textContent=connected?'● Ubuntu 接続中':'接続停止 · 表示は最終受信値';
  if(!state){$('mode').textContent='未接続';$('rviz-status').dataset.available='false';$('rviz-status').textContent='Ubuntu接続停止 · RViz2の状態を取得できません';return;}
  $('mode').textContent=state.autonomy?.profile_enabled?'実機 · 自動MVP':{simulation:'シミュレーション',live:'実機 · 走行無効',replay:'記録再生'}[state.mode]||state.mode;
  const observation=!!state.observation_only;
  $('recording-save').disabled=busy||!connected||['awaiting_sensor_data','recording','finalizing','no_sensor_data'].includes(state.recording?.phase);$('mapping-settings-save').disabled=busy||!connected||state.mapping;
  $('stop').disabled=observation;$('cancel').disabled=observation;
  $('stop').textContent=observation?'車体停止は未接続':'■ 停止';
  $('position-reference').textContent=state.pose_reference||'現在位置';
  $('implementation-scope').textContent=observation?'計測専用。位置はLiDAR中心です。取付方向・寸法は未校正、IMU融合と実機走行は無効です。':'実機の取付TF・DAC校正は準備中です。実機走行操作は無効です。';
  const navFresh=fresh('navigation'),navName=observation?({idle:'計測準備',mapping:'SLAM作成中',paused:'地図保存待ち',localization:'LiDAR位置推定',failed:'SLAM異常'}[state.slam_phase]||'計測準備'):navFresh?(names[state.nav.state]||state.nav.state||'待機中'):'状態更新停止';
  $('run-state').textContent=navName;$('mission-state').textContent=navName;
  $('map-name').textContent=state.mapping?'作成中の地図':state.map_meta?.name||'未保存の地図';
  const p=state.pose;$('position').textContent=p?`${p.x.toFixed(2)} / ${p.y.toFixed(2)}`:'— / —';$('heading').textContent=p?`${(p.yaw*180/Math.PI).toFixed(1)}°`:'—';$('velocity').textContent=p?`${Math.abs(p.v).toFixed(2)} m/s`:'—';
  $('cloud-age').textContent=state.ages.cloud===undefined?'未受信':fresh('cloud')?`${Math.round(state.ages.cloud*1000)} ms`:'更新停止';
  $('capture-status').textContent=state.mapping?'● 地図作成中':state.mapping_frames?'計測終了':'待機中';
  $('capture-time').textContent=`${Math.floor(state.mapping_seconds/60).toString().padStart(2,'0')}:${(state.mapping_seconds%60).toString().padStart(2,'0')}`;$('capture-frames').textContent=`${state.mapping_frames} ${state.observation_only?'回 地図更新':'フレーム'}`;
  $('mapping-method').textContent=state.mode==='simulation'?'点群を2D地図へ投影します。範囲20 × 20 m、解像度0.1 m。':observation?'別ウィンドウのKISS-ICP / RViz2で点群を確認します。ここでは2D SLAM地図を計測・保存します。':'外部SLAMの起動を待っています。';
  const viewer=state.viewer||{};$('rviz-status').dataset.available=String(!!viewer.available);$('rviz-status').textContent=viewer.available?'RViz2 起動中 · Ubuntuデスクトップの別ウィンドウ · 再起動: gouda.sh viewer':viewer.error||'RViz2停止中 · gouda.sh viewer で起動';
  const stationary=fresh('pose')&&p&&Math.abs(p.v)<.01&&Math.abs(p.w)<.01&&fresh('esp32')&&!state.esp.flags;
  $('mapping-start').disabled=busy||!connected||state.mapping||(observation?!fresh('lidar_raw'):!stationary||!fresh('cloud')||state.mode!=='simulation');
  $('mapping-stop').disabled=busy||!connected||!state.mapping;
  $('save-map').disabled=busy||!connected||state.mapping||!state.mapping_frames||!$('map-title').value.trim();
  $('load-map').disabled=busy||!connected||(!observation&&!stationary)||state.mapping;
  for(const b of $('saved-maps').querySelectorAll('button'))b.disabled=$('load-map').disabled;
  $('apply-pose').disabled=busy||!connected||(observation?(tool==='initial'&&!state.localization_available):!stationary);
  $('tool-start').hidden=!observation;
  const goal=state.goal,start=state.planning_start;$('target-summary').textContent=observation?((start?`計画開始  X ${start.x.toFixed(2)} / Y ${start.y.toFixed(2)} m`:'計画開始位置未設定')+' · '+(goal?`ゴール  X ${goal.x.toFixed(2)} / Y ${goal.y.toFixed(2)} m`:'ゴール未設定')):(goal?`ゴール  X ${goal.x.toFixed(2)} / Y ${goal.y.toFixed(2)} m`:'ゴール未設定');
  const observationPlanning=observation;
  const canPlan=observationPlanning?connected&&!busy&&!state.mapping&&!!state.planning_start&&!!goal&&!!state.map&&!!state.map_meta&&state.map_meta.id!=='external-map'&&!dirty&&!state.planning:connected&&stationary&&!state.mapping&&goal&&state.map&&state.map_meta&&state.nav.explicit_start&&!dirty&&!state.planning;
  $('plan').disabled=busy||!canPlan;
  let length=0;for(let i=1;i<state.path.length;i++)length+=Math.hypot(state.path[i][0]-state.path[i-1][0],state.path[i][1]-state.path[i-1][1]);
  const planReasons=[];if(!connected)planReasons.push('Ubuntuとの接続を確認してください');if(state.mapping)planReasons.push('地図作成を終了してください');if(busy&&!state.planning)planReasons.push('操作の応答を待っています');if(!state.map||!state.map_meta||state.map_meta.id==='external-map')planReasons.push('保存地図を読み込んでください');if(observationPlanning&&!state.planning_start)planReasons.push('計画開始位置を設定してください');if(!goal)planReasons.push('ゴールを設定してください');if(!observationPlanning&&!stationary)planReasons.push('停止中の車体位置とESP32応答が必要です');if(!observationPlanning&&!state.nav.explicit_start)planReasons.push('明示開始に対応したナビゲーションが必要です');if(dirty)planReasons.push('位置の変更を適用してください');if(state.planning)planReasons.push('計算中です');
  $('plan-summary').textContent=dirty?'位置が未適用です。設定ボタンで確定してください。':state.plan_error?state.plan_error:state.planning?(state.nav.state?.startsWith('PLAN_')?navName:'経路を計算しています…'):state.path.length?(observationPlanning?`地図上の経路プレビュー ${length.toFixed(2)} m · 車体の通過可否は未確認`:`予定経路 ${length.toFixed(2)} m · 走行開始待ち`):planReasons.join(' · ')||'経路を計算してください。';
  $('to-monitor').disabled=busy||!connected||!state.path.length||dirty||observation;
  const reasons=[...state.start_reasons];if(!connected)reasons.unshift('Ubuntuとの接続を確認してください');if(dirty)reasons.unshift('位置の変更を適用してください');
  $('start-reasons').textContent=reasons.length?reasons.join('\n'):'開始条件を確認しました。経路を確認して走行を開始できます。';$('start').disabled=busy||reasons.length>0;
  $('distance').textContent=p&&goal?`ゴールまで直線 ${Math.hypot(goal.x-p.x,goal.y-p.y).toFixed(2)} m`:'ゴール未設定';
  $('stop-status').textContent=connected?state.stop_status||'停止要求なし':'接続停止 · 停止状態は確認できません';
  $('map-status').textContent=!connected?'更新停止 · 最終受信データ':state.mapping?(observation?'● MAPPING · SLAM':'● MAPPING · 点群投影'):view==='3d'?(fresh('cloud')?'● POINT CLOUD':'点群更新停止'):state.map_meta?.name||'未保存の地図';
  const hasData=view==='2d'?!!state.map:state.cloud.length>0;$('map-empty').hidden=hasData;
  $('map-size').textContent=state.map?`${Number(state.map.resolution.toFixed(3))} m / cell`:'';
  $('last-update').textContent=connected?'最終受信 '+new Date().toLocaleTimeString('ja-JP'):'接続停止';
  const health=observation?[['LiDAR / 生データ','lidar_raw'],['LiDAR / 地図座標','cloud'],['IMU / 受信のみ','imu'],['LiDAR位置','pose']]:[['LiDAR / 座標変換','cloud'],['IMU','imu'],['自己位置','pose'],['ナビゲーション','navigation'],['ESP32','esp32']];$('health-list').replaceChildren();
  for(const [label,key] of health){const row=document.createElement('div');row.className='health-row';const a=document.createElement('span'),b=document.createElement('strong');a.textContent=label;b.textContent=fresh(key)?'受信中':state.ages[key]===undefined?'未受信':'更新停止';b.className=fresh(key)?'':'stale';row.append(a,b);$('health-list').append(row);}
  $('cloud-note').textContent=state.cloud_note;
  $('logs').replaceChildren();for(const log of state.logs.slice(-5).reverse()){const row=document.createElement('div');row.className='log';const t=document.createElement('time');t.textContent=new Date(log.time*1000).toLocaleTimeString('ja-JP');row.append(t,document.createTextNode(log.message));$('logs').append(row);}
}
function buildMap(){const g=state.map;mapRevision=state.map_revision;mapCache=document.createElement('canvas');mapCache.width=g.width;mapCache.height=g.height;const c=mapCache.getContext('2d'),im=c.createImageData(g.width,g.height);for(let i=0;i<g.data.length;i++){const v=g.data[i],color=v<0?[21,42,32]:v>=65?[142,179,140]:[52,78,55];const x=i%g.width,y=Math.floor(i/g.width),j=((g.height-1-y)*g.width+x)*4;im.data.set([...color,255],j);}c.putImageData(im,0,0);}
function dimensions(){return{w:canvas.clientWidth,h:canvas.clientHeight};}
function fit(){
  const {w,h}=dimensions(),g=state?.map;
  if(!(w>0&&h>0))return false;
  if(!g){camera={x:0,y:0,scale:Math.min(w,h)/12};return true;}
  let minX=g.width,minY=g.height,maxX=-1,maxY=-1;
  for(let i=0;i<g.data.length;i++)if(g.data[i]>=0){const x=i%g.width,y=Math.floor(i/g.width);minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);}
  if(maxX<0){minX=0;minY=0;maxX=g.width-1;maxY=g.height-1;}
  const cx=(minX+maxX+1)*g.resolution/2,cy=(minY+maxY+1)*g.resolution/2;
  camera.x=g.origin.x+Math.cos(g.origin.yaw)*cx-Math.sin(g.origin.yaw)*cy;
  camera.y=g.origin.y+Math.sin(g.origin.yaw)*cx+Math.cos(g.origin.yaw)*cy;
  const dx=Math.max(4,(maxX-minX+1)*g.resolution),dy=Math.max(4,(maxY-minY+1)*g.resolution);
  const c=Math.abs(Math.cos(g.origin.yaw)),t=Math.abs(Math.sin(g.origin.yaw));
  camera.scale=Math.min(w/(c*dx+t*dy),h/(t*dx+c*dy))*.82;
  return true;
}
function screen(x,y){const {w,h}=dimensions();return[w/2+(x-camera.x)*camera.scale,h/2-(y-camera.y)*camera.scale];}
function world(x,y){const {w,h}=dimensions();return{x:camera.x+(x-w/2)/camera.scale,y:camera.y-(y-h/2)/camera.scale};}
function line(points,color,width,dash=[]){if(!points?.length)return;ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();points.forEach((p,i)=>{const [x,y]=screen(...p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.stroke();ctx.setLineDash([]);}
function marker(p,color,label,robot=false){if(!p)return;const [x,y]=screen(p.x,p.y);ctx.save();ctx.translate(x,y);ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(0,0,robot?10:7,0,Math.PI*2);ctx.stroke();ctx.rotate(-p.yaw);ctx.beginPath();ctx.moveTo(robot?17:21,0);ctx.lineTo(robot?-5:13,-5);ctx.lineTo(robot?-5:13,5);ctx.closePath();ctx.fill();ctx.restore();ctx.fillStyle=color;ctx.font='11px monospace';ctx.fillText(label,x+14,robot?y-13:y+21);}
function draw(){
  if(!Number.isFinite(camera.scale)||camera.scale<=0)cameraInitialized=false;
  if(!cameraInitialized)cameraInitialized=fit();
  if(!dimensions().w||!dimensions().h)return;
  const {w,h}=dimensions(),ratio=window.devicePixelRatio||1;if(canvas.width!==Math.round(w*ratio)||canvas.height!==Math.round(h*ratio)){canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio);}ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,w,h);ctx.fillStyle='#081812';ctx.fillRect(0,0,w,h);
  if(view==='2d'){
    const g=state?.map;if(g&&mapCache){const [x,y]=screen(g.origin.x,g.origin.y);ctx.save();ctx.translate(x,y);ctx.rotate(-g.origin.yaw);ctx.imageSmoothingEnabled=false;ctx.drawImage(mapCache,0,-g.height*g.resolution*camera.scale,g.width*g.resolution*camera.scale,g.height*g.resolution*camera.scale);ctx.restore();}
    const step=camera.scale<12?5:camera.scale<25?2:1;ctx.strokeStyle='#7ea58b17';ctx.lineWidth=1;ctx.beginPath();const tl=world(0,0),br=world(w,h);for(let x=Math.floor(tl.x/step)*step;x<br.x;x+=step){const [sx]=screen(x,0);ctx.moveTo(sx,0);ctx.lineTo(sx,h);}for(let y=Math.floor(br.y/step)*step;y<tl.y;y+=step){const [,sy]=screen(0,y);ctx.moveTo(0,sy);ctx.lineTo(w,sy);}ctx.stroke();
    line(state?.trail,'#98b88780',1.5);line(dirty?[]:state?.path,'#6ae2c4',2.5,[6,4]);marker(state?.planning_start,'#92c1ee','計画START');marker(state?.goal,'#f2c979','GOAL');marker(state?.pose,fresh('pose')?'#b3f5b3':'#89958c',state?.observation_only?'LiDAR':'ROBOT',true);if(draft)marker(draft,'#92c1ee','未適用');
  }else{
    const points=state?.cloud||[];for(const p of points){const dx=p[0]-camera.x,dy=p[1]-camera.y,x=w/2+(dx-dy)*.707*camera.scale,y=h/2+(dx+dy)*.35*camera.scale-p[2]*camera.scale;ctx.fillStyle=p[2]>1.5?'#d5bf78':'#77d2a7';ctx.fillRect(x,y,2,2);}ctx.fillStyle='#92ada3';ctx.font='11px monospace';ctx.fillText('XYZ点群 / 固定斜め視点',15,50);
  }
  $('scale').textContent=`${(62/camera.scale).toFixed(1)} m`;
}
canvas.addEventListener('wheel',e=>{e.preventDefault();const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top,before=world(x,y);camera.scale=Math.min(300,Math.max(3,camera.scale*Math.exp(-e.deltaY*.001)));const after=world(x,y);camera.x+=before.x-after.x;camera.y+=before.y-after.y;draw();},{passive:false});
canvas.addEventListener('pointerdown',e=>{if(e.button!==0)return;const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;canvas.setPointerCapture(e.pointerId);pointer={x,y,start:world(x,y),camera:{...camera},id:e.pointerId};if(tool!=='pan'&&tab==='planning'&&view==='2d'){draft={...pointer.start,yaw:0};dirty=true;writePose(draft);}draw();});
canvas.addEventListener('pointermove',e=>{if(!pointer||pointer.id!==e.pointerId)return;const r=canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;if(tool==='pan'){camera.x=pointer.camera.x-(x-pointer.x)/camera.scale;camera.y=pointer.camera.y+(y-pointer.y)/camera.scale;}else if(draft){const now=world(x,y);if(Math.hypot(x-pointer.x,y-pointer.y)>5)draft.yaw=Math.atan2(now.y-draft.y,now.x-draft.x);writePose(draft);}draw();});
canvas.addEventListener('pointerup',e=>{if(!pointer||pointer.id!==e.pointerId)return;pointer=null;if(tool==='goal'&&draft)applyPose();else if(tool==='initial')notice('初期位置を指定しました。右側の設定ボタンで適用してください。');render();});
canvas.addEventListener('pointercancel',()=>{pointer=null;});
new ResizeObserver(()=>draw()).observe(canvas.parentElement);
setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('ja-JP');if(connected&&performance.now()-lastResponse>3000){connected=false;render();draw();}},1000);
poll();
