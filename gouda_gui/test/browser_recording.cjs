'use strict';
const { chromium } = require('playwright');
const base = process.argv[2] || 'http://127.0.0.1:8765';
(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage();
  let originalRecording, originalMapping, token;
  const api = async (path, data) => page.evaluate(async ({path,data}) => {
    const token=(await (await fetch('/api/session')).json()).token;
    const response=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-Gouda-Session':token},body:JSON.stringify(data)});
    return {status:response.status,body:await response.json()};
  },{path,data});
  try {
    await page.goto(base, {waitUntil: 'domcontentloaded'});
    const original=await page.evaluate(async()=>{const s=await(await fetch('/api/state')).json();return {recording:s.recording_config,mapping:s.mapping_settings?.saved};});
    originalRecording=original.recording;originalMapping=original.mapping;
    await page.getByRole('tab', {name: /記録・SLAM/}).click();
    await page.getByText('生LiDAR /lidar_points（必須）').waitFor();
    if (!(await page.locator('#rec-lidar').isChecked()) || !(await page.locator('#rec-imu').isChecked())) throw new Error('Required raw sensor topics are not selected');
    if (!(await page.locator('#rec-lidar').isDisabled()) || !(await page.locator('#rec-imu').isDisabled())) throw new Error('Required raw topics can be disabled in the GUI');

    await page.locator('#rec-glim-odom').check();
    await page.locator('#recording-save').click();
    await page.getByText(/記録設定を保存しました/).waitFor();
    const savedState=await page.evaluate(async()=>(await(await fetch('/api/state')).json()).recording_config);
    if (!savedState.topics.includes('/glim_ros/lidar_odom')) throw new Error('Saved topics were not returned');

    await page.locator('#mapping-backend').selectOption('glim_imu');
    await page.locator('#mapping-settings-save').click();
    await page.getByText(/GLIM入力設定未準備/).waitFor();
    const mapping = await page.evaluate(async () => (await (await fetch('/api/state')).json()).mapping_settings);
    if (mapping.saved.backend !== 'glim_imu' || mapping.ready) throw new Error('Unknown GLIM calibration was incorrectly marked ready');

    await page.route('**/api/state', async route => {
      const response = await route.fetch();
      const state = await response.json();
      state.recording = {phase:'no_sensor_data',directory:'/test/bags/recordings/example',elapsed_sec:15,sensor_data_seen:false,return_code:0,error:null};
      await route.fulfill({response,body:JSON.stringify(state)});
    });
    await page.getByText(/センサーの記録データを確認できません。成功した記録として扱っていません。/).waitFor();
    console.log('browser_recording: PASS');
  } finally {
    try { if (originalRecording) await api('recording_config_save',originalRecording); } catch {}
    try { if (originalMapping) await api('mapping_settings_save',originalMapping); } catch {}
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
