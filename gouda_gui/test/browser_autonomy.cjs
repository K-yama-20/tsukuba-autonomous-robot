'use strict';
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  await page.goto(process.argv[2]||'http://127.0.0.1:8766');
  await page.getByRole('tab',{name:/自動運転MVP/}).click();
  await page.locator('#autonomy-phase').waitFor();
  for(let i=0;i<50;i++){
   const t=await page.locator('#autonomy-readiness').innerText();
   if(t.includes('gouda.sh autonomy'))break;
   await new Promise(r=>setTimeout(r,100));
  }
  assert.equal(await page.locator('#autonomy-start').isDisabled(),true);
  assert.equal(await page.locator('#autonomy-tx').inputValue(),'');
  assert.equal(await page.locator('#autonomy-quat').inputValue(),'');
  const result=await page.evaluate(async()=>{
   const token=(await(await fetch('/api/session')).json()).token;
   const response=await fetch('/api/autonomy_start',{method:'POST',headers:{'Content-Type':'application/json','X-Gouda-Session':token},body:JSON.stringify({goal:{forward_m:1,left_m:0,yaw_rad:0},target_v_mps:.2,target_w_rps:.3})});
   return {status:response.status,body:await response.json()};
  });
  assert.notEqual(result.status,200);assert.match(JSON.stringify(result.body),/プロファイル/);
  const state=await page.evaluate(async()=>(await(await fetch('/api/state')).json()));
  assert.equal(state.autonomy.profile_enabled,false);
  assert.equal(state.autonomy.settings.saved.body_to_lidar,null);
  for(const topic of ['/gouda/control/drive','/gouda/control/reference','/gouda/control/estimate','/gouda/control/manual_input','/gouda/control_trace','/gouda/autonomy/state'])assert(state.recording_config.topics.includes(topic));
  await page.reload();assert.equal(errors.length,0,errors.join('\n'));
  console.log('browser_autonomy: PASS (unknown mounts, no implicit start, analysis topics)');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
