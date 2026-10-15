const msg = (t) => (document.getElementById("msg").textContent = t);
const apiInput = document.getElementById("api");
chrome.storage.local.get("api").then((v) => { if (v.api) apiInput.value = v.api; });

document.getElementById("maps").onclick = async () => {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    msg("Reading the Maps list (scrolling to load more)...");
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["maps.js"] });
    const [{ result: rows }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, func: () => scrapeMapsRows() });
    const base = apiInput.value.replace(/\/$/, "");
    await chrome.storage.local.set({ api: base });
    const query = decodeURIComponent((tab.url.match(/maps\/search\/([^/@?]+)/) || [, ""])[1]).replace(/\+/g, " ");
    const r = await fetch(`${base}/leads/ingest`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rows, query }) });
    const j = await r.json();
    msg(r.ok ? `Sent ${j.received}: ${j.new} new, ${j.updated} already known. Open Maps Leads in the app.` : `App error: ${JSON.stringify(j)}`);
  } catch (e) { msg(String(e.message || e)); }
};

document.getElementById("go").onclick = async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const pages = Number(document.getElementById("pages").value) || 1;
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["scrape.js"] });
  const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: tab.id }, args: [pages], func: (n) => scrapeAll(n) });
  const url = URL.createObjectURL(new Blob([result], { type: "text/csv" }));
  Object.assign(document.createElement("a"), { href: url, download: "page.csv" }).click();
  msg(`${result.split("\n").length - 1} rows exported`);
};
