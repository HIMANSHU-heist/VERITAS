const ALLOW = [
  "https://veritas-trading.web.app",
  "https://veritas-trading.firebaseapp.com",
  "http://localhost:8000",
];
const hits = new Map();

const SYSTEM =
  "You are Ask VERITAS, a friendly assistant on a PAPER-trading " +
  "research dashboard. " +
  "1) For questions about VERITAS (decisions, dates, P&L, gates, " +
  "how it works) use ONLY the provided context. If a fact is not " +
  "in the context, say you don't have it. Never invent VERITAS " +
  "numbers. " +
  "2) For any other question (general knowledge, market concepts, " +
  "coding, anything) answer normally from your own knowledge. " +
  "3) Never give personal investment advice or tell the user to " +
  "buy or sell a real security. " +
  "Be simple and short. ALWAYS reply in English, even if the user " +
  "writes in romanized Marathi or Hindi (Hinglish). Reply in another " +
  "language only if the user explicitly asks for it or writes in " +
  "that language's own script.";

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const cors = {
      "Access-Control-Allow-Origin": ALLOW.includes(origin) ? origin : ALLOW[0],
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Allow-Methods": "POST,OPTIONS",
      "Vary": "Origin",
    };
    const json = (o, s = 200) =>
      new Response(JSON.stringify(o), {
        status: s,
        headers: { ...cors, "Content-Type": "application/json" },
      });

    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return json({ error: "no" }, 405);
    if (!ALLOW.includes(origin)) return json({ error: "forbidden" }, 403);

    const ip = req.headers.get("CF-Connecting-IP") || "x";
    const now = Date.now();
    const arr = (hits.get(ip) || []).filter((t) => now - t < 60000);
    if (arr.length >= 15) {
      return json({ answer: "Too many questions, please wait a minute." });
    }
    arr.push(now);
    hits.set(ip, arr);
    if (hits.size > 5000) hits.clear();

    let b;
    try {
      b = await req.json();
    } catch (e) {
      return json({ error: "bad" }, 400);
    }
    const question = String(b.question || "").slice(0, 600);
    const ctx = JSON.stringify(b.context || {}).slice(0, 12000);
    const hist = Array.isArray(b.history) ? b.history.slice(-4) : [];

    const messages = [{ role: "system", content: SYSTEM }];
    for (const h of hist) {
      messages.push({ role: "user", content: String(h.q || "").slice(0, 300) });
      messages.push({ role: "assistant", content: String(h.a || "").slice(0, 500) });
    }
    messages.push({
      role: "user",
      content:
        "Question: " + question +
        "\n\nVERITAS context (use only for VERITAS questions):\n" + ctx,
    });

    try {
      const r = await fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + env.GROQ_API_KEY,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "openai/gpt-oss-120b",
          temperature: 0.3,
          max_tokens: 900,
          reasoning_effort: "low",
          messages: messages,
        }),
      });
      const j = await r.json();
      const answer = j.choices && j.choices[0] && j.choices[0].message
        ? j.choices[0].message.content
        : null;
      return json({ answer: answer });
    } catch (e) {
      return json({ answer: null });
    }
  },
};
