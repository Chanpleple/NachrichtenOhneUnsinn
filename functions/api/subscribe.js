const PUBLIC_KEY = "BOJTzsASZnhToYFcuzKZD-ZvgD3s-WaYyZy89wCncaMoC301S0C7fhNyYd5LO2LjCxE8W8oPjrsvWItu1-6z_NY";
const json=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const b64url=b=>btoa(String.fromCharCode(...new Uint8Array(b))).split('+').join('-').split('/').join('_').replace(/=+$/, '');
export async function onRequestGet(){return json({publicKey:PUBLIC_KEY});}
export async function onRequestPost({request,env}){
 if(!env.PUSH_SUBSCRIPTIONS)return json({error:"Push storage is not configured"},503);
 let data;try{data=await request.json()}catch{return json({error:"Invalid JSON"},400)}
 const sub=data.subscription;
 if(!sub||typeof sub.endpoint!=="string"||!sub.keys?.p256dh||!sub.keys?.auth)return json({error:"Invalid push subscription"},400);
 const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(sub.endpoint));
 const id=b64url(digest);
 await env.PUSH_SUBSCRIPTIONS.put(id,JSON.stringify({subscription:sub,breakingOnly:data.breakingOnly!==false,createdAt:new Date().toISOString()}));
 return json({ok:true});
}
