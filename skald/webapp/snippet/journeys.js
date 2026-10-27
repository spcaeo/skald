/* Skald recorded journeys: docs/JOURNEYS.md. Consented events only, posted to the site's own
relay (it adds the address and signs). Before consent nothing is stored and nothing is sent. */
((w,d,n)=>{
var J=w.skaldJourneys;if(J&&J.on)return;// loaded twice
var Q=(J&&J.q)||[],no=()=>!1;
if(n.doNotTrack=="1"||w.doNotTrack=="1"||n.globalPrivacyControl){w.skaldJourneys={on:1,consent:no,track:no,withdraw:()=>Promise.resolve(!1),state:()=>({consent:!1,off:!0})};return}
var S=d.currentScript,L=location,H=history,LS,A=k=>S&&S.getAttribute("data-"+k),
RELAY=A("relay")||"/api/skald-journey",WD=A("withdraw")||RELAY+"/withdraw",NOTE=txt(A("notice"),80),
KV="skald.j.v",KC="skald.j.c",KS="skald.j.s",IDLE=18e5,
EV=["cta_click","form_sent","signup","booking_opened","booking_made","download"],EM=["form_sent","signup","booking_made"],
UU=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,SV=/^skv_[\w-]{22}$/,
MAIL=/^[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$/,HOST=/^[a-z0-9]([a-z0-9.-]{0,198}[a-z0-9])?$/,
on=0,vid,sid,at,last,T={},P=new URLSearchParams(L.search),r,h,
bare=x=>x.replace(/^www\./,""),cur=()=>path(L.pathname);
try{LS=w.localStorage}catch{}
var get=k=>{try{return LS.getItem(k)}catch{}},put=(k,v)=>{try{LS.setItem(k,v)}catch{}};
// Kept in page memory only until consent: where this visit came from.
T.landing_path=cur();
try{r=new URL(d.referrer);h=r.hostname.toLowerCase();
if(bare(h)!=bare(L.hostname.toLowerCase())&&HOST.test(h)&&!/\.\.|^[\d.]+$/.test(h))T.referrer={host:h,path:path(r.pathname)}}catch{}
["source","medium","campaign","content","term"].forEach(k=>{var v=txt(P.get("utm_"+k),160);if(v)T["utm_"+k]=v});
function dec(s){try{return decodeURIComponent(s)}catch{return s}}
// The contract refuses a text that may name a person (contract.personal): such text is left out.
function per(t){return/@|\d{7,}|(?:\d[\s()+.-]*){10,}|[A-Za-z0-9_]{40,}/.test(t)||/(^|[^\w.])(\d{1,3}\.){3}\d{1,3}(?![\w.])/.test(t)||/(^|[^0-9a-f:])[0-9a-f]{0,4}(:[0-9a-f]{0,4}){2,}/i.test(t)}
function txt(v,most){v=v==null?"":String(v).trim();return v&&v.length<=most&&!/[\x00-\x1f\x7f]/.test(v)&&!per(dec(v))?v:""}
// The page's path only; a part that may name a person becomes "-".
function path(p){p=String(p||"/").replace(/\/+/g,"/").split("/").map(s=>{var t=dec(s);return/[?#\\\x00-\x1f]/.test(t)||t.split("/").includes("..")||per(t)?"-":s}).join("/").slice(0,500);return p.replace(/\/+$/,"")||"/"}
function uid(){var c=w.crypto,b,x;if(c.randomUUID)return c.randomUUID();b=c.getRandomValues(new Uint8Array(16));b[6]=b[6]&15|64;b[8]=b[8]&63|128;
x=[...b].map(v=>(v+256).toString(16).slice(1)).join("");return[x.slice(0,8),x.slice(8,12),x.slice(12,16),x.slice(16,20),x.slice(20)].join("-")}
// A session ends after 30 minutes without an event (shared by the site's tabs).
function ses(){var now=Date.now(),s=(get(KS)||sid+"|"+at).split("|"),fresh=!UU.test(s[0])||!(now-s[1]<IDLE);sid=fresh?uid():s[0];at=now;put(KS,sid+"|"+at);return fresh}
function post(u,b,again){try{return fetch(u,{method:"POST",keepalive:!0,credentials:"same-origin",headers:{"Content-Type":"application/json"},body:b})
.then(r=>{if(!again&&(r.status==429||r.status>=500))retry(u,b);return r.ok},()=>{again||retry(u,b);return!1})}catch{return Promise.resolve(!1)}}
// Once more with the same body (Skald keeps an event once by its ID); never after another 4xx.
var retry=(u,b)=>setTimeout(()=>post(u,b,1),3e3);
function emit(name,x){var e={schema_version:1,event_id:uid(),event_name:name,occurred_at:new Date().toISOString().slice(0,19)+"Z",
visitor_id:vid,session_id:sid,path:cur(),consent:{analytics:"granted"}},k=get("skald.vid");
if(NOTE)e.consent.notice_version=NOTE;if(SV.test(k))e.skald_vid=k;for(k in x)e[k]=x[k];post(RELAY,JSON.stringify(e))}
function go(name,x){if(!on)return;var t=T||{landing_path:cur()};T=0;if(ses())emit("session_started",{touch:t});emit(name,x||{})}
function pv(){var p=cur();if(on&&p!=last){last=p;go("page_view")}}
function drop(){on=0;vid=sid=at=last=null;[KV,KC,KS].forEach(k=>{try{LS.removeItem(k)}catch{}})}
function grant(g){if(!g)return drop();if(on)return;on=1;put(KC,NOTE||"1");var v=get(KV);vid=UU.test(v)?v:vid||uid();put(KV,vid);pv()}
function track(name,o){o=o||{};var x={},l=txt(o.label,80),m=typeof o.email=="string"?o.email.trim():"";
if(!on||!EV.includes(name))return!1;if(l)x.label=l;if(m&&m.length<=254&&EM.includes(name)&&MAIL.test(m))x.email=m;go(name,x);return!0}
function withdraw(){var v=vid||get(KV);drop();if(!UU.test(v))return Promise.resolve(!0);
try{return fetch(WD,{method:"POST",keepalive:!0,credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({visitor_id:v})}).then(r=>r.ok,no)}catch{return Promise.resolve(!1)}}
["pushState","replaceState"].forEach(k=>{var f=H[k];H[k]=function(){var r=f.apply(this,arguments);pv();return r}});
w.addEventListener("popstate",pv);w.addEventListener("pageshow",e=>{if(e.persisted){last=null;pv()}});
var api=w.skaldJourneys={on:1,consent:g=>grant(!!g),track,withdraw,state:()=>({consent:!!on,visitor_id:on?vid:null,session_id:on&&sid||null,notice:NOTE||null})};
// Consent remembered for the same notice, or decided by the site before this script loaded.
if(get(KC)==(NOTE||"1")&&UU.test(get(KV))||A("consent")=="granted")grant(1);
Q.forEach(q=>{try{api[q[0]](...q.slice(1))}catch{}});
})(window,document,navigator);
