import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const enc = new TextEncoder();
const b64u = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");

async function hmac(secret:string, data:string) {
  const key=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);
  return b64u(new Uint8Array(await crypto.subtle.sign("HMAC",key,enc.encode(data))));
}
Deno.serve(async (req) => {
  const cors={"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"content-type","Access-Control-Allow-Methods":"POST,OPTIONS"};
  if(req.method==="OPTIONS") return new Response("ok",{headers:cors});
  if(req.method!=="POST") return new Response("Method not allowed",{status:405,headers:cors});
  try{
    const {assertion,token,user_agent}=await req.json();
    if(!assertion || !token || token.length>4096) throw new Error("bad request");
    const [body,sig]=String(assertion).split(".");
    const secret=Deno.env.get("PUSH_REGISTRATION_SECRET")!;
    if(!secret || !sig || (await hmac(secret,body))!==sig) return new Response("Unauthorized",{status:401,headers:cors});
    const pad="=".repeat((4-body.length%4)%4);
    const payload=JSON.parse(atob(body.replace(/-/g,"+").replace(/_/g,"/")+pad));
    if(!["player","founder"].includes(payload.typ) || !payload.sub || Number(payload.exp)<Date.now()/1000)
      return new Response("Expired",{status:401,headers:cors});
    const db=createClient(Deno.env.get("SUPABASE_URL")!,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    const {error}=await db.from("push_subscriptions").upsert({
      identity_type:payload.typ, identity_id:String(payload.sub), fcm_token:String(token),
      user_agent:String(user_agent||"").slice(0,500), is_active:true, updated_at:new Date().toISOString()
    },{onConflict:"fcm_token"});
    if(error) throw error;
    return new Response(JSON.stringify({ok:true}),{headers:{...cors,"Content-Type":"application/json"}});
  }catch(e){return new Response("Bad request",{status:400,headers:cors});}
});
