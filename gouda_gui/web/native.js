import RFB from '/native/vendor/core/rfb.js';
import { encodings } from '/native/vendor/core/encodings.js';
// noVNC 1.3 advertises JPEG-capable Tight by default. Negotiate only lossless
// framebuffer encodings; point geometry and RViz RGB pixels are never altered.
class LosslessRFB extends RFB {
  _sendEncodings(){
    const e=encodings;
    RFB.messages.clientEncodings(this._sock,[e.encodingCopyRect,e.encodingHextile,e.encodingRRE,e.encodingRaw,
      e.pseudoEncodingDesktopSize,e.pseudoEncodingLastRect,e.pseudoEncodingQEMUExtendedKeyEvent,
      e.pseudoEncodingExtendedDesktopSize,e.pseudoEncodingFence,e.pseudoEncodingContinuousUpdates,
      e.pseudoEncodingDesktopName,e.pseudoEncodingCursor]);
  }
}
const host=document.getElementById('native-screen');
const status=document.getElementById('native-status');
let rfb=null, linked=false, retryAt=0;
function active(){return document.body.classList.contains('native-active');}
function connect(){
  if(rfb||!active()||Date.now()<retryAt)return;
  rfb=new LosslessRFB(host,`${location.protocol==='https:'?'wss':'ws'}://${location.host}/native/ws`);
  rfb.background='rgb(0, 0, 0)';rfb.scaleViewport=true;rfb.resizeSession=false;rfb.viewOnly=false;
  rfb.addEventListener('connect',()=>{linked=true;});
  rfb.addEventListener('disconnect',()=>{linked=false;rfb=null;retryAt=Date.now()+3000;status.textContent='更新停止 · 画面へ再接続しています';});
  rfb.addEventListener('securityfailure',()=>{status.textContent='画面接続を確認できません';});
}
async function check(){
  connect();
  try{
    const r=await fetch('/api/viewer',{signal:AbortSignal.timeout(1500)});
    if(!r.ok)throw new Error();
    const s=await r.json();
    status.textContent=!s.available?'更新停止 · RViz2が停止しています':!linked?'画面への接続待ち':!s.fresh?'更新停止 · KISS-ICPの点群を待っています':'KISS-ICP / RViz2 · 標準表示 · マウスで回転・移動・拡大';
    status.dataset.fresh=String(linked&&s.available&&s.fresh);
  }catch{status.textContent='更新停止 · 画面転送への接続を確認してください';status.dataset.fresh='false';}
  setTimeout(check,1000);
}
new MutationObserver(()=>{if(active())connect();else rfb?.blur();}).observe(document.body,{attributes:true,attributeFilter:['class']});
window.addEventListener('beforeunload',()=>rfb?.disconnect());
check();
