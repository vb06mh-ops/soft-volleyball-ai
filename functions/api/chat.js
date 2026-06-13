import { CHAT_SYSTEM, callAI, json } from "./_shared.js";

const MAX_CHAT_MESSAGES = 30;

export async function onRequestPost({ request, env }) {
  try {
    const body = await request.json().catch(() => ({}));
    let raw = Array.isArray(body.messages) ? body.messages : [];
    const messages = raw.slice(-MAX_CHAT_MESSAGES).filter(m => m && typeof m === "object").map(m => ({
      role: m.role === "assistant" ? "assistant" : "user",
      content: String(m.content || "").slice(0, 4000)
    }));
    const text = await callAI(messages, CHAT_SYSTEM, env, 600);
    return json({ success: true, message: text });
  } catch (e) {
    return json({ success: false, error: String(e.message || e) }, 500);
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" } });
}
