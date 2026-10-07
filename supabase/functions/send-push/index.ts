import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

import { isStaff } from "../_shared/access.ts";
const enc=new TextEncoder();
const b64url=(b:Uint8Array)=>btoa(String.fromCharCode(...b)).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
async function accessToken(){
  const email=Deno.env.get("FIREBASE_CLIENT_EMAIL")!, pk=Deno.env.get("FIREBASE_PRIVATE_KEY")!.replace(/\\n/g,"\n");
  const now=Math.floor(Date.now()/1000);
  const head=b64url(enc.encode(JSON.stringify({alg:"RS256",typ:"JWT"})));
  const body=b64url(enc.encode(JSON.stringify({iss:email,scope:"https://www.googleapis.com/auth/firebase.messaging",aud:"https://oauth2.googleapis.com/token",iat:now,exp:now+3600})));
  const key=await crypto.subtle.importKey("pkcs8",pem(pk),{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["sign"]);
  const sig=b64url(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",key,enc.encode(`${head}.${body}`))));
  const r=await fetch("https://oauth2.googleapis.com/token",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:new URLSearchParams({grant_type:"urn:ietf:params:oauth:grant-type:jwt-bearer",assertion:`${head}.${body}.${sig}`})});
  if(!r.ok) throw new Error("oauth");
  return (await r.json()).access_token;
}
function pem(p:string){const b=atob(p.replace(/-----[^-]+-----/g,"").replace(/\s/g,""));return Uint8Array.from(b,c=>c.charCodeAt(0)).buffer}
Deno.serve(async(req)=>{
  if(req.method!=="POST") return new Response("Method not allowed",{status:405});
  if(!Deno.env.get("PUSH_SEND_SECRET") || req.headers.get("X-LD-Push-Secret")!==Deno.env.get("PUSH_SEND_SECRET")) return new Response("Unauthorized",{status:401});
  try{
    const {identity_type,identity_id,title,body}=await req.json();
    if(!["player","founder"].includes(identity_type) || !identity_id) throw new Error("bad target");
    const db=createClient(Deno.env.get("SUPABASE_URL")!,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
    let recipientIds: string[] = [];
    if (identity_type === "founder") {
      if (identity_id !== "founder") throw new Error("bad target");
      const {data: players, error} = await db.from("players").select("activision_id,status,org_role").eq("status","Approved");
      if (error) throw error;
      recipientIds = (players || []).filter(isStaff).map(p => p.activision_id);
    } else {
      const {data: player, error} = await db.from("players").select("status").eq("activision_id",String(identity_id)).maybeSingle();
      if (error || player?.status !== "Approved") return new Response("Forbidden",{status:403});
      recipientIds = [String(identity_id)];
    }
    if (!recipientIds.length) return new Response(JSON.stringify({ok:true,sent:0}),{headers:{"Content-Type":"application/json"}});
    const {data,error} = await db.from("push_subscriptions").select("id,fcm_token,identity_id")
      .eq("identity_type","player").in("identity_id",recipientIds).eq("is_active",true);
    if(error) throw error;
    if (!data?.length) return new Response(JSON.stringify({ok:true,sent:0}),{headers:{"Content-Type":"application/json"}});
    const oauth=await accessToken(), project=Deno.env.get("FIREBASE_PROJECT_ID")!;
    let sent=0;
    for(const row of data||[]){
      const {data: current, error: currentError} = await db.from("players").select("status,org_role")
        .eq("activision_id",row.identity_id).maybeSingle();
      if (currentError || current?.status !== "Approved" || (identity_type === "founder" && !isStaff(current))) continue;
      const {data: active, error: activeError} = await db.from("push_subscriptions").select("id")
        .eq("id",row.id).eq("identity_type","player").eq("identity_id",row.identity_id).eq("is_active",true).maybeSingle();
      if (activeError || !active) continue;
      const r=await fetch(`https://fcm.googleapis.com/v1/projects/${project}/messages:send`,{
        method:"POST",headers:{"Authorization":`Bearer ${oauth}`,"Content-Type":"application/json"},
        body:JSON.stringify({message:{token:row.fcm_token,data:{identity_type,identity_id:String(identity_id),title:String(title||"Last Demons").slice(0,100),body:identity_type === "founder" ? "Nuovo aggiornamento nell’area organizzazione." : String(body||"").slice(0,500)},webpush:{headers:{TTL:"300"}}}})
      });
      if(r.ok) sent++; else if([404,410].includes(r.status)) await db.from("push_subscriptions").update({is_active:false}).eq("id",row.id);
    }
    return new Response(JSON.stringify({ok:true,sent}),{headers:{"Content-Type":"application/json"}});
  }catch(e){return new Response("Push failed",{status:500});}
});
