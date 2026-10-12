/* Skald beacon-only mode, docs/BEACON.md. No cookie, no storage. */
(function(w,d,n){if(n.doNotTrack=="1"||w.doNotTrack=="1"||n.globalPrivacyControl||!n.sendBeacon)return;
var s=d.currentScript,u=s&&s.getAttribute("data-endpoint")||"/traffic-beacon",t0,last,L=location,
q=(new URLSearchParams(L.search).get("utm_source")||"").toLowerCase().slice(0,60),r="";
try{r=new URL(d.referrer).hostname.toLowerCase().replace(/^www\./,"");if(r==L.hostname.replace(/^www\./,""))r=""}catch(e){}
function send(e,id){var x=w.innerWidth,b={e:e,p:L.pathname,vw:x<480?"xs":x<768?"sm":x<1024?"md":x<1440?"lg":"xl",
t:Math.min(86400,Math.round((Date.now()-t0)/1e3))};if(id)b.id=id;if(r)b.r=r;if(q)b.u=q;
n.sendBeacon(u,new Blob([JSON.stringify(b)],{type:"text/plain"}))}
function pv(){if(L.pathname!=last){last=L.pathname;t0=Date.now();send("page_view")}}
var p=history.pushState;history.pushState=function(){p.apply(this,arguments);pv()};
w.addEventListener("popstate",pv);w.skald=send;pv()})(window,document,navigator);
