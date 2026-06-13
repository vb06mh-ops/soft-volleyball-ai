import { MODULE_PROMPTS, PROMPT_BUILDERS, callAI, extractJson, sanitizeData, json } from "./_shared.js";

export async function onRequestPost({ request, env }) {
  try {
    const body = await request.json().catch(() => ({}));
    const module = String(body.module || "diagnose").slice(0, 40);
    const data = sanitizeData(body.data || {});
    const builder = PROMPT_BUILDERS[module];
    if (!builder) return json({ success: false, error: "unknown module" }, 400);
    const prompt = builder(data);
    const system = MODULE_PROMPTS[module] || MODULE_PROMPTS.diagnose;
    const text = await callAI([{ role: "user", content: prompt }], system, env, 8000, true);
    return json({ success: true, result: extractJson(text) });
  } catch (e) {
    let msg = String(e.message || e);
    if (msg.includes("429") || msg.toLowerCase().includes("quota")) msg = "本日の無料利用枠を使い切りました（429）。明日リセットされます。";
    else if (msg.includes("503")) msg = "AIが混雑しています（503）。30秒ほど待って再度お試しください。";
    return json({ success: false, error: msg }, 500);
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" } });
}
