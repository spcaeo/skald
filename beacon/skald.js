/* Skald beacon-only, docs/BEACON.md. No cookie, no storage. */
(function(w,d,n){if(n.doNotTrack=="1"||w.doNotTrack=="1"||n.globalPrivacyControl||!n.sendBeacon)return;
var u=d.currentScript?.dataset.endpoint||"/traffic-beacon",t,l,L=location,H=history,
lc=h=>(h||"").toLowerCase(),bare=h=>lc(h).replace(/^www\./,""),
q=lc(new URLSearchParams(L.search).get("utm_source")).slice(0,60),r="",
send=(e,id)=>{var x=w.innerWidth,b={e,p:L.pathname,vw:x<480?"xs":x<768?"sm":x<1024?"md":x<1440?"lg":"xl",
t:Math.min(86400,Math.round((Date.now()-t)/1e3))};if(id)b.id=id;if(r)b.r=r;if(q)b.u=q;
n.sendBeacon(u,new Blob([JSON.stringify(b)],{type:"text/plain"}))},
pv=()=>{if(L.pathname!=l){l=L.pathname;t=Date.now();send("page_view")}};
try{r=bare(new URL(d.referrer).hostname);if(r==bare(L.hostname))r=""}catch{}
["pushState","replaceState"].forEach(k=>{var f=H[k];H[k]=(...a)=>{f.apply(H,a);pv()}});
["popstate","pageshow"].forEach(k=>w.addEventListener(k,e=>pv(e.persisted&&(l=0))));
w.skald=send;pv()})(window,document,navigator);
