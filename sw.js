const C='fsv8',SHELL=['/','/index.html','/manifest.json','/icon.svg','/icon-192.png','/icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(C).then(c=>Promise.allSettled(SHELL.map(u=>c.add(u)))).then(()=>self.skipWaiting()))});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',e=>{const r=e.request,u=new URL(r.url);
if(r.method!=='GET'||u.origin!==location.origin||u.pathname.startsWith('/api')||u.pathname.startsWith('/admin'))return;
e.respondWith(fetch(r).then(x=>{if(x.ok){const c=x.clone();caches.open(C).then(h=>h.put(r,c))}return x}).catch(()=>caches.match(r).then(m=>m||(r.mode==='navigate'?caches.match('/index.html'):Response.error()))))});
