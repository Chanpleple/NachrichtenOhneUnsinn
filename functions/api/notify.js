const PUBLIC_KEY="BOJTzsASZnhToYFcuzKZD-ZvgD3s-WaYyZy89wCncaMoC301S0C7fhNyYd5LO2LjCxE8W8oPjrsvWItu1-6z_NY";
const enc=new TextEncoder();
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).split('+').join('-').split('/').join('_').replace(/=+$/, '');
const fromB64u=s=>Uint8Array.from(atob(s.replace(/-/g,"+").replace(/_/g,"/")+"=".repeat((4-s.length%4)%4)),c=>c.charCodeAt(0));
const concat=(...parts)=>{const n=parts.reduce((s,p)=>s+p.length,0),o=new Uint8Array(n);let i=0;for(const p of parts){o.set(p,i);i+=p.length;}return o;};
async function hmac(key,data){const k=await crypto.subtle.importKey("raw",key,{name:"HMAC",hash:"SHA-256"},false,["sign"]);return new Uint8Array(await crypto.subtle.sign("HMAC",k,data));}
async function hkdf(ikm,salt,info,len){const prk=await hmac(salt,ikm);let t=new Uint8Array(0),out=new Uint8Array(0),c=1;while(out.length<len){t=await hmac(prk,concat(t,info,new Uint8Array([c++])));out=concat(out,t);}return out.slice(0,len);}
async function vapidJwt(endpoint,env){
 const aud=new URL(endpoint).origin,now=Math.floor(Date.now()/1000);
 const header=b64u(enc.encode(JSON.stringify({typ:"JWT",alg:"ES256"})));
 const pub=fromB64u(PUBLIC_KEY),priv=fromB64u(env.VAPID_PRIVATE_KEY);
 const jwk={kty:"EC",crv:"P-256",x:b64u(pub.slice(1,33)),y:b64u(pub.slice(33,65)),d:b64u(priv),ext:true};
 const key=await crypto.subtle.importKey("jwk",jwk,{name:"ECDSA",namedCurve:"P-256"},false,["sign"]);
 const body=b64u(enc.encode(JSON.stringify({aud,exp:now+43200,sub:env.VAPID_SUBJECT||"mailto:admin@akhbar-blaharaa.pages.dev"})));
 const input=header+"."+body;
 const sig=await crypto.subtle.sign({name:"ECDSA",hash:"SHA-256"},key,enc.encode(input));
 return input+"."+b64u(sig);
}
async function encryptPayload(subscription,payload){
 const ua=fromB64u(subscription.keys.p256dh),auth=fromB64u(subscription.keys.auth);
 const uaKey=await crypto.subtle.importKey("raw",ua,{name:"ECDH",namedCurve:"P-256"},false,[]);
 const server=await crypto.subtle.generateKey({name:"ECDH",namedCurve:"P-256"},true,["deriveBits"]);
 const as=new Uint8Array(await crypto.subtle.exportKey("raw",server.publicKey));
 const shared=new Uint8Array(await crypto.subtle.deriveBits({name:"ECDH",public:uaKey},server.privateKey,256));
 const ikm=await hkdf(shared,auth,concat(enc.encode("WebPush: info\0"),ua,as),32);
 const salt=crypto.getRandomValues(new Uint8Array(16));
 const cek=await hkdf(ikm,salt,enc.encode("Content-Encoding: aes128gcm\0"),16);
 const nonce=await hkdf(ikm,salt,enc.encode("Content-Encoding: nonce\0"),12);
 const plain=concat(enc.encode(JSON.stringify(payload)),new Uint8Array([2]));
 const aes=await crypto.subtle.importKey("raw",cek,{name:"AES-GCM"},false,["encrypt"]);
 const cipher=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce,tagLength:128},aes,plain));
 const rs=new Uint8Array([0,0,16,0]);
 return concat(salt,rs,new Uint8Array([as.length]),as,cipher);
}
async function sendOne(record,payload,env){
 const sub=record.subscription,body=await encryptPayload(sub,payload),jwt=await vapidJwt(sub.endpoint,env);
 return fetch(sub.endpoint,{method:"POST",headers:{"Authorization":"vapid t="+jwt+", k="+PUBLIC_KEY,"TTL":"86400","Content-Encoding":"aes128gcm","Content-Type":"application/octet-stream"},body});
}
const json=(d,s=200)=>new Response(JSON.stringify(d),{status:s,headers:{"content-type":"application/json","cache-control":"no-store"}});
export async function onRequestPost({request,env}){
 if(!env.PUSH_SUBSCRIPTIONS||!env.VAPID_PRIVATE_KEY||!env.NOTIFY_TOKEN)return json({error:"Push service is not fully configured"},503);
 if(request.headers.get("authorization")!=="Bearer "+env.NOTIFY_TOKEN)return json({error:"Unauthorized"},401);
 let data;try{data=await request.json()}catch{return json({error:"Invalid JSON"},400)}
 const articles=Array.isArray(data.articles)?data.articles.slice(0,30):[];
 if(!articles.length)return json({ok:true,sent:0,reason:"No new articles"});
 const listed=await env.PUSH_SUBSCRIPTIONS.list({limit:1000});
 let sent=0,removed=0,failed=0;
 for(const key of listed.keys){
  const raw=await env.PUSH_SUBSCRIPTIONS.get(key.name);if(!raw)continue;
  let record;try{record=JSON.parse(raw)}catch{await env.PUSH_SUBSCRIPTIONS.delete(key.name);removed++;continue;}
  const selected=articles.filter(a=>!record.breakingOnly||/عاجل|breaking|urgent|تطور عاجل/i.test((a.title||"")+" "+(a.description||"")));
  if(!selected.length)continue;
  const a=selected[0];
  try{const response=await sendOne(record,{title:"🔴 "+(a.title||"خبر جديد"),body:(a.source||"أخبار بلا هراء")+" · اضغط لقراءة الخبر",url:a.url||"https://akhbar-blaharaa.pages.dev/"},env);
   if(response.ok)sent++;else if(response.status===404||response.status===410){await env.PUSH_SUBSCRIPTIONS.delete(key.name);removed++;}else failed++;
  }catch{failed++;}
 }
 return json({ok:true,sent,removed,failed});
}
