import { JOURNAL_SYSTEM, buildJournalPrompt, callAI, json } from "./_shared.js";

export async function onRequestPost({ request, env }) {
  try {
    const body = await request.json().catch(() => ({}));
    const entries = Array.isArray(body.entries) ? body.entries.slice(-60) : [];
    const prompt = buildJournalPrompt(entries);
    const text = await callAI([{ role: "user", content: prompt }], JOURNAL_SYSTEM, env, 1200);
    return json({ success: true, analysis: text });
  } catch (e) {
    return json({ success: false, error: String(e.message || e) }, 500);
  }
}

export async function onRequestOptions() {
  return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" } });
}
