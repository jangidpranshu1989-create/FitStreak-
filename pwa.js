(()=>{
if(matchMedia('(display-mode: standalone)').matches||navigator.standalone)return;
let ev=null;const ios=/iphone|ipad|ipod/i.test(navigator.userAgent),snoozed=()=>Date.now()-(+localStorage.getItem('pwa-no')||0)<6048e5;
const b=document.createElement('button');b.hidden=true;b.textContent='Install app';
b.style.cssText='position:fixed;left:50%;bottom:104px;transform:translateX(-50%);z-index:80;padding:12px 22px;border-radius:99px;border:0;background:#ececee;color:#121212;font:700 14px system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.35)';
document.body.appendChild(b);
addEventListener('beforeinstallprompt',e=>{e.preventDefault();ev=e;if(!snoozed())b.hidden=false});
b.onclick=async()=>{if(ev){ev.prompt();const r=await ev.userChoice;ev=null;b.hidden=true;if(r.outcome!=='accepted')localStorage.setItem('pwa-no',Date.now())}else if(ios){alert('Tap the Share button, then choose "Add to Home Screen".');b.hidden=true;localStorage.setItem('pwa-no',Date.now())}};
addEventListener('appinstalled',()=>{b.hidden=true;ev=null});
if(ios&&!snoozed()){b.textContent='Add to Home Screen';b.hidden=false}
})();
