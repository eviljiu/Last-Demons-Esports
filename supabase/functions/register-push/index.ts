import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const enc = new TextEncoder();
const cors = {
  "Access-Control-Allow-Origin": "https://last-demons.web.app",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST,OPTIONS",
};
const b64u = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

async function hmac(secret: string, data: string) {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  return b64u(new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(data))));
}

function response(message: string, status: number) {
  return new Response(message, { status, headers: cors });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return response("ok", 200);
  if (req.method !== "POST") return response("Method not allowed", 405);

  try {
    const data = await req.json();
    const assertion = String(data?.assertion || "");
    // Companion uses fcm_token; keep token as backwards-compatible fallback.
    const token = String(data?.fcm_token || data?.token || "");
    const userAgent = String(data?.user_agent || "").slice(0, 500);

    if (!assertion || !token || token.length > 4096) return response("Invalid request", 400);

    const parts = assertion.split(".");
    if (parts.length !== 2) return response("Invalid assertion", 400);
    const [body, sig] = parts;

    const secret = Deno.env.get("PUSH_REGISTRATION_SECRET") || "";
    if (!secret) return response("Server configuration error", 500);
    if ((await hmac(secret, body)) !== sig) return response("Unauthorized", 401);

    const pad = "=".repeat((4 - body.length % 4) % 4);
    const payload = JSON.parse(atob(body.replace(/-/g, "+").replace(/_/g, "/") + pad));

    // Current Streamlit assertion names. Legacy typ/sub remain accepted during rollout.
    const identityType = String(payload.identity_type || payload.typ || "");
    const identityId = String(payload.identity_id || payload.sub || "");
    const exp = Number(payload.exp || 0);

    if (!["player", "founder"].includes(identityType) || !identityId)
      return response("Invalid identity", 400);
    if (!Number.isFinite(exp) || exp < Date.now() / 1000)
      return response("Expired", 401);

    const db = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );
    const { error } = await db.from("push_subscriptions").upsert({
      identity_type: identityType,
      identity_id: identityId,
      fcm_token: token,
      user_agent: userAgent,
      is_active: true,
      updated_at: new Date().toISOString(),
    }, { onConflict: "fcm_token" });

    if (error) {
      console.error("push_subscriptions upsert:", error.message);
      return response("Database registration failed", 500);
    }

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("register-push:", e instanceof Error ? e.message : String(e));
    return response("Bad request", 400);
  }
});
