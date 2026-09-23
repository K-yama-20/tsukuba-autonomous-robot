const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8766');
 await page.waitForFunction(()=>document.querySelector('#connection').textContent.includes('接続中'),null,{timeout:30000});
 await page.waitForFunction(()=>document.querySelector('#native-screen canvas')?.width===1280,null,{timeout:60000});
 // A ServerInit-sized canvas can still be an empty framebuffer while Qt starts.
 // Require actual native window pixels, without generating any sensor data.
 const waitForNativePixels=async()=>{
  await page.waitForFunction(()=>{
   const c=document.querySelector('#native-screen canvas');if(!c||c.width!==1280)return false;
   const pixels=c.getContext('2d').getImageData(0,0,c.width,100).data;
   let painted=0;for(let i=0;i<pixels.length;i+=64)if(pixels[i]+pixels[i+1]+pixels[i+2]>80)painted++;
   return painted>500;
  },null,{timeout:60000});
  await page.waitForFunction(()=>document.querySelector('#native-status').textContent.includes('更新停止'),null,{timeout:15000});
 };
 await waitForNativePixels();
 const state=await page.request.get('http://127.0.0.1:8766/api/state').then(r=>r.json());
 assert.equal(state.mode,'live');assert.equal(state.observation_only,true);
 assert.equal(state.pose,null);assert.equal(state.map,null);assert.equal(state.mapping_frames,0);
 assert.ok(await page.locator('#mapping-start').isDisabled());
 const viewer=await page.request.get('http://127.0.0.1:8766/api/viewer').then(r=>r.json());
 assert.equal(viewer.available,true);assert.equal(viewer.fresh,false);
 const canvas=page.locator('#native-screen canvas');const box=await canvas.boundingBox();
 await page.mouse.move(box.x+box.width*.65,box.y+box.height*.55);
 await page.mouse.wheel(0,-200);
 await page.mouse.down();await page.mouse.move(box.x+box.width*.7,box.y+box.height*.6,{steps:5});await page.mouse.up();
 await page.screenshot({path:'/tmp/gouda-smoke/native.png'});
 for(let i=0;i<3;i++){
  await page.locator('#tab-planning').click();
  await page.waitForFunction(()=>!document.body.classList.contains('native-active'));
  await page.locator('#tab-mapping').click();
 }
 await page.reload();
 await waitForNativePixels();
 assert.equal((await page.request.get('http://127.0.0.1:8766/api/state',{headers:{Origin:'http://untrusted.invalid'}})).status(),403);
 assert.equal((await page.request.get('http://127.0.0.1:8766/api/unknown')).status(),404);
 await page.setViewportSize({width:390,height:844});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 await browser.close();console.log('PASS: no invented map/pose, native RViz, tabs, reconnect, origin guards');
})().catch(e=>{console.error(e);process.exit(1)});
