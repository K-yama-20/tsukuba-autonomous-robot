'use strict';
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const base = process.argv[2] || 'http://127.0.0.1:8766';
(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  let originalRecording, originalMapping, sessionDirectory;
  const api = async (route, data) => page.evaluate(async ({route,data}) => {
    const token=(await (await fetch('/api/session')).json()).token;
    const response=await fetch('/api/'+route,{method:'POST',headers:{'Content-Type':'application/json','X-Gouda-Session':token},body:JSON.stringify(data)});
    return {status:response.status,body:await response.json()};
  },{route,data});
  const state = () => page.evaluate(async()=>(await(await fetch('/api/state')).json()));
  const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
  const pollState = async (predicate, description, timeoutMs) => {
    const deadline=Date.now()+timeoutMs;let latest;
    while(Date.now()<deadline){latest=await state();if(predicate(latest))return latest;await sleep(250);}
    throw new Error(`Timed out waiting for ${description}; last state: ${JSON.stringify(latest?.recording)}`);
  };
  try {
    await page.goto(base, {waitUntil:'domcontentloaded'});
    await page.getByRole('tab',{name:/記録・SLAM/}).click();
    await page.locator('#recording-phase').waitFor();
    const initial=await state();
    originalRecording=initial.recording_config;
    originalMapping=initial.mapping_settings?.saved;
    if (!['idle','failed','completed'].includes(initial.recording?.phase)) throw new Error('Recording manager is not idle before the no-input capture test: '+JSON.stringify(initial.recording));
    if (initial.ages?.lidar_raw!==undefined || initial.ages?.imu!==undefined) {
      throw new Error('No-input capture test requires raw LiDAR and IMU topics to be absent');
    }
    if (!(await page.locator('#rec-lidar').isChecked()) || !(await page.locator('#rec-imu').isChecked()) || !(await page.locator('#rec-tf').isChecked())) throw new Error('Required raw sensor/TF topics are not selected');
    if (!(await page.locator('#rec-lidar').isDisabled()) || !(await page.locator('#rec-imu').isDisabled()) || !(await page.locator('#rec-tf').isDisabled())) throw new Error('Required raw topics can be disabled in the GUI');

    await page.locator('#rec-glim-odom').check();
    await page.locator('#rec-storage').selectOption('sqlite3');
    await page.locator('#rec-duration').fill('1');
    await page.locator('#rec-size').fill('1');
    await page.locator('#rec-disk').fill('1');
    await page.locator('#recording-save').click();
    await page.getByText(/記録設定を保存しました/).waitFor();
    let saved=await state();
    if (!saved.recording_config.topics.includes('/glim_ros/lidar_odom') || saved.recording_config.storage_id!=='sqlite3') throw new Error('Recording settings did not persist');

    await page.locator('#mapping-backend').selectOption('glim_imu');
    for (const id of ['map-tx','map-ty','map-tz','map-quat','map-lidar-offset','map-imu-offset']) await page.locator('#'+id).fill('');
    for (const id of ['map-point-mode','map-point-field','map-point-type','map-point-time','map-accel-unit','map-gyro-unit']) await page.locator('#'+id).selectOption('unknown');
    await page.locator('#mapping-settings-save').click();
    await page.getByText(/GLIM入力設定未準備/).waitFor();
    let mapping=await state();
    if (mapping.mapping_settings.saved.backend!=='glim_imu' || mapping.mapping_settings.ready) throw new Error('UNKNOWN GLIM calibration was incorrectly marked ready');
    await page.reload({waitUntil:'domcontentloaded'});
    await page.getByRole('tab',{name:/記録・SLAM/}).click();
    await page.locator('#recording-phase').waitFor();
    if (!(await page.locator('#rec-glim-odom').isChecked()) || await page.locator('#rec-storage').inputValue()!=='sqlite3' || await page.locator('#mapping-backend').inputValue()!=='glim_imu') throw new Error('Saved settings did not survive page reload');
    mapping=await state();
    if (mapping.mapping_settings.ready) throw new Error('UNKNOWN GLIM calibration became ready after reload');

    const previousDirectory=saved.recording?.directory||null;
    const startedAt=Date.now();
    await page.locator('#recording-start').click();
    await pollState(s=>s.recording?.directory&&s.recording.directory!==previousDirectory&&['awaiting_sensor_data','recording','no_sensor_data'].includes(s.recording.phase),'a new recording session to start',15000);
    let capture=await pollState(s=>s.recording?.directory&&s.recording.directory!==previousDirectory&&s.recording.phase==='no_sensor_data'&&s.recording.elapsed_sec>=15,'15 seconds without raw sensor data',45000);
    sessionDirectory=capture.recording.directory;
    if (Date.now()-startedAt<15000 || capture.recording.sensor_data_seen) throw new Error('No-input state arrived before 15 seconds or unexpectedly observed sensor data');
    await page.locator('#recording-stop').click();
    capture=await pollState(s=>s.recording?.directory===sessionDirectory&&['failed','completed'].includes(s.recording.phase)&&s.recording.return_code!==null&&s.recording.return_code!==undefined,'the recorder to finish finalization',60000);
    if (capture.recording.phase==='completed' || capture.recording.metadata_verified || capture.recording.sensor_data_seen) throw new Error('Empty capture was reported as successful');
    if (capture.recording.phase!=='failed' || capture.recording.return_code===null || capture.recording.return_code===undefined) throw new Error('No-input capture did not finish as a verified failure: '+JSON.stringify(capture.recording));
    if ((await page.locator('#recording-phase').innerText()).includes('記録完了')) throw new Error('UI reported success for an empty capture');

    await page.setViewportSize({width:390,height:844});
    if (await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth)) throw new Error('Recording tab overflows on a mobile-width viewport');
    console.log('browser_recording: PASS');
  } finally {
    try {
      const current=await state();
      if (['recording','awaiting_sensor_data','no_sensor_data','finalizing'].includes(current.recording?.phase)) {
        await api('recording_stop',{});
        await pollState(s=>['failed','completed'].includes(s.recording?.phase)&&s.recording.return_code!==null&&s.recording.return_code!==undefined,'recording cleanup in test teardown',60000);
      }
    } catch {}
    try { if (originalRecording) await api('recording_config_save',originalRecording); } catch {}
    try { if (originalMapping) await api('mapping_settings_save',originalMapping); } catch {}
    if (sessionDirectory) {
      const workspace=path.resolve(process.env.GOUDA_TEST_WORKSPACE||process.env.GOUDA_WORKSPACE||path.join(os.homedir(),'gouda_ws'));
      const recordings=path.resolve(workspace,'bags','recordings');
      const target=path.resolve(sessionDirectory);
      if (path.dirname(target)===recordings && path.basename(target).startsWith('gouda_')) await fs.rm(target,{recursive:true,force:true});
    }
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exit(1);});
