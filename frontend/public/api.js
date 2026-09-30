/* Thin REST + real-time client. No frameworks - Option A (beginner/local). */
const API = {
  base: "",
  token: localStorage.getItem("rsvp_token") || null,
  setToken(t) { this.token = t; t ? localStorage.setItem("rsvp_token", t) : localStorage.removeItem("rsvp_token"); },
  async req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.token) headers["Authorization"] = "Bearer " + this.token;
    const res = await fetch(this.base + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) { const err = new Error(data?.error?.message || "Request failed"); err.code = data?.error?.code; err.status = res.status; err.extra = data?.error; throw err; }
    return data;
  },
  get(p) { return this.req("GET", p); },
  post(p, b) { return this.req("POST", p, b); },
  put(p, b) { return this.req("PUT", p, b); },
  del(p) { return this.req("DELETE", p); },
};

/* Real-time: try WebSocket first, gracefully fall back to polling (Approach 1 vs Approach 3, section 8). */
function connectEventRealtime(eventId, onUpdate) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  let ws, poll, closed = false;
  function startPolling() {
    if (poll) return;
    poll = setInterval(async () => { try { onUpdate(await API.get(`/api/events/${eventId}`)); } catch (_) {} }, 4000);
  }
  try {
    ws = new WebSocket(`${proto}://${location.host}/ws/events/${eventId}?token=${API.token || ""}`);
    ws.onmessage = (ev) => onUpdate(JSON.parse(ev.data));
    ws.onerror = () => { if (!closed) startPolling(); };
    ws.onclose = () => { if (!closed) startPolling(); };
    const keepAlive = setInterval(() => { if (ws.readyState === 1) ws.send("ping"); }, 20000);
    return () => { closed = true; clearInterval(keepAlive); clearInterval(poll); ws.close(); };
  } catch (_) {
    startPolling();
    return () => { closed = true; clearInterval(poll); };
  }
}
