import json
import sys
import time
import urllib.request

B = "https://pipeline-api-dnnk.onrender.com"


def call(path, method="GET", body=None):
    req = urllib.request.Request(B + path, json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"}, method=method)
    return json.load(urllib.request.urlopen(req, timeout=120))


def run(stage, limit=None, source=None):
    jid = call("/control/jobs", "POST", {"stage": stage, "limit": limit, "source": source, "dry_run": False})["id"]
    while True:
        j = call(f"/control/jobs/{jid}")
        if j["status"] in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(5)
    bad = [x["message"] for x in j["logs"] if x["level"] != "info"][:3]
    print(f"{stage:16} {j['status']:10} {j['stats'].get('counts')} {bad} {(j['error'] or '')[-150:]}", flush=True)
    return j


gh = ["stripe", "airbnb", "figma", "discord", "databricks", "cloudflare", "coinbase", "reddit", "robinhood", "instacart",
      "dropbox", "asana", "gitlab", "mongodb", "twilio", "datadog", "okta", "pinterest", "lyft", "doordash", "brex", "gusto"]
call("/control/sources/ycombinator", "PUT", {"enabled": True, "rate_limit_seconds": 1, "query_filters": {}})
call("/control/sources/greenhouse", "PUT", {"enabled": True, "rate_limit_seconds": 1, "query_filters": {"slugs": gh}})
call("/control/sources/lever", "PUT", {"enabled": True, "rate_limit_seconds": 1, "query_filters": {"slugs": ["spotify", "palantir", "plaid", "netlify"]}})
call("/control/sources/ashby", "PUT", {"enabled": True, "rate_limit_seconds": 1, "query_filters": {"slugs": ["ramp", "notion", "linear", "openai", "retool", "deel"]}})
call("/control/sources/sec_edgar", "PUT", {"enabled": True, "rate_limit_seconds": 1, "query_filters": {"sic_codes": [7372, 7374, 6199, 6282], "max_companies": 30}})
call("/control/sources/press_rss", "PUT", {"enabled": True, "rate_limit_seconds": 1})

run("discover", 120)
run("resolve_domains", 40)
for _ in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3):
    run("find_contacts", 40)
    run("verify_email", 200)
run("enrich", 120)
run("rank")
run("draft", 80)
p = call("/people?min_score=1")
print("people:", len(p), "by intent:", {k: sum(1 for x in p if x["intent"] == k) for k in ("hire", "invest", "advise")})
print("companies:", call("/companies?page_size=1")["total"], "drafts:", len(call("/drafts?status=pending")))
