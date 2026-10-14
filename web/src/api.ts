// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type J = Record<string, any>;

export function token(): string {
  try { return localStorage.getItem("control_token") ?? ""; } catch { return ""; }
}

function headers(): Record<string, string> {
  const t = token();
  return { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

export async function api<T = J>(path: string, method = "GET", body?: unknown): Promise<T> {
  const r = await fetch(`/api${path}`, { method, headers: headers(), body: body === undefined ? undefined : JSON.stringify(body) });
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* keep default */ }
    throw new Error(msg);
  }
  return r.status === 204 ? (undefined as T) : r.json();
}

/** SSE over fetch so the bearer token header can be sent (EventSource cannot). */
export async function streamSSE(path: string, onEvent: (event: string, data: J) => void, signal: AbortSignal): Promise<void> {
  const r = await fetch(`/api${path}`, { headers: headers(), signal });
  if (!r.ok || !r.body) throw new Error(`stream failed: ${r.status}`);
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += value;
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const ev = /^event: (.*)$/m.exec(chunk)?.[1] ?? "message";
      const data = /^data: (.*)$/m.exec(chunk)?.[1];
      if (data) onEvent(ev, JSON.parse(data));
    }
  }
}
