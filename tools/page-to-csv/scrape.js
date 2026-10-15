// Core logic, injected into the page. Idea: the data you want is the biggest group of sibling elements that look alike.
function detectRows() {
  const sig = (el) => el.tagName + "." + [...el.classList].sort().join(".");
  let best = { score: 0, rows: [] };
  for (const parent of document.querySelectorAll("table tbody, table, ul, ol, div, section, main")) {
    const groups = new Map();
    for (const c of parent.children) {
      if (!c.innerText || !c.innerText.trim()) continue;
      const k = sig(c);
      groups.set(k, [...(groups.get(k) || []), c]);
    }
    for (const rows of groups.values()) {
      const score = rows.length >= 3 ? rows.length * Math.log(2 + rows.reduce((n, r) => n + r.innerText.length, 0) / rows.length) : 0;
      if (score > best.score) best = { score, rows };
    }
  }
  return best.rows;
}

function rowToCells(row) {
  const cells = [];
  const kids = [...row.children];
  const parts = kids.length > 1 ? kids : [row];
  for (const p of parts) {
    const text = p.innerText.replace(/\s+/g, " ").trim();
    if (text) cells.push(text);
  }
  const links = [...row.querySelectorAll("a[href]")].map((a) => a.href);
  return { cells, links: [...new Set(links)] };
}

function toCsv(rows) {
  const data = rows.map(rowToCells);
  const nText = Math.max(0, ...data.map((d) => d.cells.length));
  const nLink = Math.max(0, ...data.map((d) => d.links.length));
  const header = [...Array(nText).keys()].map((i) => `col${i + 1}`).concat([...Array(nLink).keys()].map((i) => `link${i + 1}`));
  const esc = (v = "") => `"${String(v).replace(/"/g, '""')}"`;
  return [header, ...data.map((d) => [...Array.from({ length: nText }, (_, i) => d.cells[i]), ...Array.from({ length: nLink }, (_, i) => d.links[i])])]
    .map((r) => r.map(esc).join(",")).join("\n");
}

async function scrapeAll(maxPages = 1, waitMs = 1500) {
  const seen = new Set(), out = [];
  for (let page = 0; page < maxPages; page++) {
    for (const r of detectRows()) { const t = r.innerText; if (!seen.has(t)) { seen.add(t); out.push(r); } }
    const next = [...document.querySelectorAll("a,button")].find((b) => /^(next|›|»|older)\b/i.test((b.innerText || b.ariaLabel || "").trim()) && !b.disabled);
    if (!next || page === maxPages - 1) break;
    next.click();
    await new Promise((r) => setTimeout(r, waitMs));
  }
  return toCsv(out);
}
