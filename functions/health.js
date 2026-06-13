export async function onRequestGet({ env }) {
  return new Response(JSON.stringify({ status: "ok", api_key_configured: !!env.GEMINI_API_KEY }), {
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}
