// Google Maps results mode. Run on a Maps search page (left list). Maps changes its markup often: if a field comes back empty,
// inspect the card in DevTools and adjust the selector. The key column is has_website: businesses with no Website button.
async function scrapeMapsRows(maxScrolls = 40) {
  const feed = document.querySelector('div[role="feed"]');
  if (!feed) throw new Error("Open a Google Maps search (the results list on the left) first");
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  let last = 0, idle = 0;
  for (let i = 0; i < maxScrolls && idle < 3; i++) {
    feed.scrollTo(0, feed.scrollHeight);
    await sleep(1400);
    const n = feed.querySelectorAll("a.hfpxzc").length;
    idle = n === last ? idle + 1 : 0;
    last = n;
    if (/reached the end of the list/i.test(feed.innerText)) break;
  }
  const phoneRe = /(\+?\d[\d\s().-]{7,}\d)/;
  const rows = [...feed.querySelectorAll("a.hfpxzc")].map((a) => {
    const card = a.closest('div[role="article"]') || a.parentElement;
    const lines = card.innerText.split("\n").map((s) => s.trim()).filter(Boolean);
    const rm = lines.map((l) => l.match(/^(\d\.\d)\((\d[\d,]*)\)$/)).find(Boolean); // Maps shows "4.7(888)"
    const rating = rm ? `${rm[1]} stars ${rm[2]} Reviews` : card.querySelector('span[role="img"]')?.getAttribute("aria-label") || "";
    const site = card.querySelector('a[data-value="Website"], a[aria-label*="Website"]');
    return {
      name: a.getAttribute("aria-label") || lines[0] || "",
      rating,
      category_address: lines.find((l) => l.includes("·")) || "",
      phone: (card.innerText.match(phoneRe) || [""])[0].trim(),
      has_website: site ? "yes" : "no",
      website: site ? site.href : "",
      maps_url: a.href,
    };
  });
  return rows;
}

async function scrapeMaps() {
  const rows = await scrapeMapsRows();
  const esc = (v = "") => `"${String(v).replace(/"/g, '""')}"`;
  const cols = ["name", "rating", "category_address", "phone", "has_website", "website", "maps_url"];
  return [cols, ...rows.map((r) => cols.map((c) => r[c]))].map((r) => r.map(esc).join(",")).join("\n");
}
