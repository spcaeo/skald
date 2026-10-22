/* Skald: docs/INTEGRATIONS.md "The script tag". First-party ID; never reads a field's value. */
((w,d,n)=>{
if((w.skald||0).on)return;// loaded twice
var IDS=1,S=d.currentScript,L=location,H=history,Q=(w.skald&&w.skald.q)||[],LS,SS,T;
try{LS=w.localStorage;SS=w.sessionStorage}catch{}
if(n.doNotTrack=="1"||w.doNotTrack=="1"||n.globalPrivacyControl){w.skald=()=>null;return}
var lc=s=>String(s||"").toLowerCase(),ga=(el,k)=>el.getAttribute(k),A=k=>S&&ga(S,"data-"+k),
on=(t,e,f,c)=>t.addEventListener(e,f,c),bare=h=>lc(h).replace(/^www\./,""),
END=A("endpoint")||ep(),SITE=lc(A("site")),ok=A("consent")!="required",
SH=A("share-subdomains")=="true",LD=lc(A("link-domains")).split(/\s*,\s*/),K="skald.vid",
vid,from,last,t0=Date.now(),seen=[],
CAL={event_type_viewed:"open",date_and_time_selected:"time_selected",event_scheduled:"booked"},
tok=v=>lc(v).replace(/[^a-z0-9_.:-]+/g,"_").replace(/^[^a-z0-9]+/,"").slice(0,60),
ends=(h,m)=>!!m&&(h==m||h.slice(-m.length-1)=="."+m),OK=/^skv_[\w-]{22}$/,P=new URLSearchParams(L.search),IN=P.get("skv"),RH="";
try{RH=lc(new URL(d.referrer).hostname)}catch{}
// post beside the script
function ep(m){m=S&&/^(https?:\/\/[^/]+)(.*)\/traffic-js\/[^/?#]*/.exec(S.src);return(m?(m[1]==L.origin?"":m[1])+m[2]:"")+"/traffic-beacon"}
// ?skv=<id> from another of your domains: adopt it, drop it from the address
if(OK.test(IN)&&(A("accept-id")=="true"||LD.some(m=>ends(RH,m)))){P.delete("skv");P+="";try{H.replaceState(H.state,"",L.pathname+(P&&"?"+P)+L.hash)}catch{}}else IN=0;
// Cookie domain: data-site if it holds this host, else 2 labels (3 after co.uk etc)
function dom(){var h=L.hostname,p=h.split(".");if(ends(h,SITE))return SITE;
if(p.length<2||/^[\d.]+$|:/.test(h))return"";
return p.slice(/^(co|com|net|org|gov|ac|edu)\.[a-z]{2}$/.test(p.slice(-2).join("."))?-3:-2).join(".")}
function ck(v,age){var m=dom();d.cookie="skald_vid="+v+";path=/;max-age="+age+(m?";domain="+m:"")+";samesite=lax;secure"}
var make=()=>"skv_"+btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(16)))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
function id(){if(!IDS||!ok)return null;if(vid)return vid;
var c=SH&&(d.cookie.match(/\bskald_vid=(skv_[\w-]{22})/)||[])[1],l;
try{l=LS.getItem(K)}catch{}
try{vid=IN||c||(OK.test(l)?l:make());LS.setItem(K,vid)}catch{}
if(vid&&SH)ck(vid,34560000);return vid||null}
function drop(){vid=from=last=IN=null;try{LS.removeItem(K);SS.removeItem("skald.src")}catch{}if(SH)ck("",0)}
function src(){if(from)return from;
var r="",u=lc(new URLSearchParams(L.search).get("utm_source")),o;
r=bare(RH);if(r==bare(L.hostname))r="";
try{if(r||u)SS.setItem("skald.src",r+" "+u);else{o=(SS.getItem("skald.src")||" ").split(" ");r=o[0];u=o[1]}}catch{}
return from=[r,u]}
function go(e,i){if(!ok||!e)return;
var x=w.innerWidth,v=id(),o=src(),j,b={e:e,p:L.pathname.slice(0,300),
vw:x<480?"xs":x<768?"sm":x<1024?"md":x<1440?"lg":"xl",t:Math.min(86400,Math.max(0,Math.round((Date.now()-t0)/1e3)))};
if(i=tok(i))b.id=i;if(o[0])b.r=o[0];if(o[1])b.u=o[1];if(v)b.v=v;j=JSON.stringify(b);
try{if(n.sendBeacon(END,new Blob([j],{type:"text/plain"})))return}catch{}
try{fetch(END,{method:"POST",body:j,keepalive:!0}).catch(()=>0)}catch{}}
function pv(){if(!ok||L.pathname==last)return;last=L.pathname;t0=Date.now();seen=[];go("page_view");clearTimeout(T);T=setTimeout(scan,50)}
var once=(k,e)=>{if(ok&&!seen.includes(k)){seen.push(k);go(e)}},nf=()=>d.querySelector('[data-skald="404"]')&&once(404,"404_view"),
scan=()=>{em();nf()};
function tag(u){var v=id(),h=lc(u.hostname),p=u.searchParams,ch=0;if(!v)return"";
if(ends(h,"calendly.com")&&!p.get("utm_content")){p.set("utm_content",v);ch=1}
LD.forEach(m=>{if(ends(h,m)&&!p.get("skv")){p.set("skv",v);ch=1}});return ch?u.href:""}
function em(){if(!id())return;
d.querySelectorAll('iframe[src*="calendly.com"],[data-url*="calendly.com"]').forEach(f=>{
var k=f.tagName=="IFRAME"?"src":"data-url",x;try{x=tag(new URL(ga(f,k),L.href))}catch{}if(x)f.setAttribute(k,x)})}
function form(t){var f=t&&t.form;while(!f&&t&&t.tagName!="FORM")t=t.parentNode;f=f||t;
return f&&ga(f,"data-skald")!="off"&&ga(f,"role")!="search"?f:null}
var fe=(f,s,k)=>go(((k=ga(f,"data-skald"))=="signup"||s=="submit"&&/^(contact|waitlist)$/.test(k)?k:"form")+"_"+s,ga(f,"id")||ga(f,"name")||"form");
on(d,"focusin",ev=>{var f=form(ev.target);if(f&&!seen.includes(f)){seen.push(f);fe(f,"start")}},!0);
on(d,"submit",ev=>{var f=form(ev.target);if(f)fe(f,"submit")},!0);
on(d,"click",ev=>{var el,a,c,u,x;
for(el=ev.target;el&&el.getAttribute;el=el.parentNode){c=c||ga(el,"data-skald-cta");if(!a&&el.tagName=="A"&&el.href)a=el}
if(c)go("cta_click",c);if(!a)return;try{u=new URL(a.href,L.href)}catch{return}
x=u.protocol;if(x=="tel:")return go("tel_click");if(x=="mailto:")return go("mailto_click");
if(!/^https?:$/.test(x)||u.hostname==L.hostname)return;
x=tag(u);if(x)a.href=x;go("outbound_click",bare(u.hostname))},!0);
on(w,"message",ev=>{var o=ev.origin,m=ev.data||{},t=m.type,c=/^calendly\./.test(m.event)&&CAL[m.event.slice(9)];
if(o=="https://calendly.com")go(c&&"calendly_"+c);
else if(o=="https://app.cal.com")go(t=="linkReady"?"cal_open":/^bookingSuccessful/.test(t)&&"cal_booked");
else if(/^https:\/\/meetings(-\w+)?\.hubspot\.com$/.test(o)&&(m.meetingBookSucceeded||m.meetingsPayload))go("hubspot_meeting_booked")});
["pushState","replaceState"].forEach(k=>{var f=H[k];H[k]=function(){f.apply(this,arguments);pv()}});
// back/forward; a page restored from the back-forward cache is opened again
on(w,"popstate",pv);on(w,"pageshow",e=>{if(e.persisted){last=null;pv()}});
on(d,"copy",()=>once("c","copy_text"));
on(w,"scroll",()=>w.scrollY+w.innerHeight>=.75*d.documentElement.scrollHeight&&once("s","scroll_75"),{passive:!0});
new MutationObserver(()=>{clearTimeout(T);T=setTimeout(scan,50)}).observe(d.documentElement,{childList:!0,subtree:!0});
function api(c,a,b){if(c=="id")return id();
if(c=="consent"){if(ok=!!a){pv();em()}else drop();return}
if(c=="track")return go(tok(a),b&&b.id);go(tok(c),a)}
(w.skald=api).on=1;pv();Q.forEach(q=>api(...q));
d.readyState=="loading"?on(d,"DOMContentLoaded",scan):em();
})(window,document,navigator);
