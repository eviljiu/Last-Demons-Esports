import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const enc = new TextEncoder();

const corsHeaders = {
  "Access-Control-Allow-Origin": "https://last-demons.web.app",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function makeResponse(body: string, status = 200, contentType = "text/plain; charset=utf-8") {
  return new Response(body, {
    status,
    headers: { ...corsHeaders, "Content-Type": contentType },
  });
}

const b64u = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

async function hmac(secret: string, data: string) {
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(data));
  return b64u(new Uint8Array(sig));
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return makeResponse("ok", 200);
  if (req.method !== "POST") return makeResponse("Method not allowed", 405);

  try {
    const data = await req.json();
    const assertion = String(data?.assertion ?? "");
    const token = String(data?.fcm_token ?? data?.token ?? "");
    const userAgent = String(data?.user_agent ?? "").slice(0, 500);

    if (!assertion || !token || token.length > 4096) {
      return makeResponse("Invalid request", 400);
    }

    const parts = assertion.split(".");
    if (parts.length !== 2) return makeResponse("Invalid assertion", 400);
    const [body, sig] = parts;

    const secret = Deno.env.get("PUSH_REGISTRATION_SECRET") ?? "";
    if (!secret) return makeResponse("Server configuration error", 500);

    const expected = await hmac(secret, body);
    if (expected !== sig) return makeResponse("Unauthorized", 401);

    const pad = "=".repeat((4 - (body.length % 4)) % 4);
    const decoded = body.replace(/-/g, "+").replace(/_/g, "/") + pad;
    const payload = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(decoded), c => c.charCodeAt(0))));

    const identityType = String(payload?.identity_type ?? payload?.typ ?? "");
    const identityId = String(payload?.identity_id ?? payload?.sub ?? "");
    const exp = Number(payload?.exp ?? 0);

    if (identityType !== "player" || !identityId || payload?.v !== 2) {
      return makeResponse("Invalid identity", 400);
    }
    if (!Number.isFinite(exp) || exp < Date.now() / 1000) {
      return makeResponse("Expired", 401);
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    if (!supabaseUrl || !serviceKey) {
      return makeResponse("Server configuration error", 500);
    }

    const db = createClient(supabaseUrl, serviceKey);

    const { data: player, error } = await db.from("players").select("id,status,password_hash")
      .eq("activision_id", identityId).maybeSingle();
    if (error || player?.status !== "Approved") return makeResponse("Forbidden", 403);
    const digest = await crypto.subtle.digest("SHA-256", enc.encode(`${player.id}:${player.password_hash || ""}`));
    const stamp = Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
    if (payload.auth !== stamp) return makeResponse("Session expired", 403);
    const { error: writeError } = await db.rpc("ld_register_push_identity", {
      p_identity_type: identityType, p_identity_id: identityId,
      p_token: token, p_user_agent: userAgent,
    });

    if (writeError) {
      console.error("push write", writeError.code, writeError.message);
      return makeResponse(`Database registration failed: ${writeError.code ?? "db_write_error"}`, 500);
    }

    return makeResponse(JSON.stringify({ ok: true }), 200, "application/json; charset=utf-8");
  } catch (err) {
    console.error("register-push", err instanceof Error ? err.message : String(err));
    return makeResponse("Bad request", 400);
  }
});
