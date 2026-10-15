# Page to CSV (learning project)

A tiny Chrome extension in the spirit of Instant Data Scraper: it finds the biggest group of look-alike elements on the page
you have open (a table, or a list of cards), turns each into a CSV row (text columns + link columns), and can follow "Next".

Load it: chrome://extensions, turn on Developer mode, Load unpacked, pick this folder, then click the extension on a page.

How it works: `scrape.js` -> `detectRows()` groups siblings by tag + class and scores groups by row count and text size;
`rowToCells()` reads each row; `toCsv()` escapes and joins; `scrapeAll()` clicks "Next" and de-duplicates rows.
Limits: no infinite scroll, no shadow DOM, pages that load rows late need a longer wait. Use it only on pages you may copy.
