"""Leads, /for/ pages and first-touch drafts for every employer whose posting maps to a built tool.

Writes leads.csv, drafts/<tool>/<slug>.md (DRAFT — NOT SENT) and each tool repo's
leads.json (read by its scripts/build_page.py to make /for/<token>/ pages that open on
the employer's own posting line). Nothing here contacts anyone.
"""
import csv, hashlib, json, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESK = ROOT.parent
NEEDS = {x["need"]: x for x in json.loads((ROOT / "data" / "needs.json").read_text())}
TOOLS = {
    "paperwork-sorter": {"needs": ["organize and file business documents", "enter data into business systems", "process vendor invoices and payments"],
                         "site": "https://paperwork-sorter.vercel.app", "name": "Paperwork Sorter", "items": "documents", "free": "The first 3 documents are free",
                         "example": "a pile of invoices, W-9s and an insurance certificate"},
    "estimate-drafter": {"needs": ["draft project estimates and proposals"], "site": "https://estimate-drafter-mn.vercel.app",
                         "name": "Estimate Drafter", "items": "requests", "free": "The first request is free", "example": "a tree company's price list and two customer requests"},
    "report-from-export": {"needs": ["build reports from business data", "analyze performance data for insights", "analyze costs and profit margins"],
                           "site": "https://report-from-export.vercel.app", "name": "Report From Export", "items": "rows", "free": "The first 200 rows are free",
                           "example": "a service company's work-order export"},
}
JUNK = {"administration dept"}
# The quote must name the tool's own step; a field tech "documenting findings" is not a paperwork pile.
FIT = {"paperwork-sorter": re.compile(r"invoice|w-?9|insurance|paperwork|\bfil(e|es|ing)\b|scan|data entry|organi[sz]|packing slip|purchase order|\bpo'?s\b|titles|submittals|onboard|enter", re.I),
       "estimate-drafter": re.compile(r"quote|estimat|\bbid|takeoff|pricing|proposal|change order", re.I),
       "report-from-export": re.compile(r"report|metric|analy[sz]|statistic|cost control|variance|margin|spend", re.I)}
SKIP = re.compile(r"monthly payment|GIS|student will|close the deal|training|security officer|assist estimators|partnering with", re.I)
# A duty that is about a person, a meeting, or presence, not the tool's step, does not make a lead.
OFFTOPIC = re.compile(r"\b(abuse|neglect|train|greet|walk|drive|supervis|lead the|meet with|present to)\b", re.I)


def posted_label(p):
    try:
        return datetime.fromisoformat(p.replace("Z", "+00:00")[:19]).strftime("%B %Y")
    except Exception:
        return "October 2026"


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:50]


def main():
    rows = []
    for tool, cfg in TOOLS.items():
        by = {}
        for n in cfg["needs"]:
            for q in NEEDS[n]["quotes"]:
                emp = (q["employer"] or "").strip()
                if emp.lower() in JUNK or OFFTOPIC.search(q["quote"]) or not FIT[tool].search(q["quote"]) or SKIP.search(q["quote"]):
                    continue
                key = emp.lower() or "anon:" + q["quote"].strip().lower()  # a reposted Craigslist ad is one lead
                score = len(FIT[tool].findall(q["quote"])) * 100 + min(len(q["quote"]), 99)
                if key not in by or score > by[key]["_s"]:  # the line that names the step most plainly
                    q = {**q, "_s": score}
                    by[key] = {**q, "need": n}
        leads = []
        for key, q in sorted(by.items()):
            emp = (q["employer"] or "").strip()
            token = hashlib.sha1(f"{tool}|{key}".encode()).hexdigest()[:8]
            title = re.sub(r"\s+", " ", q["title"]).strip()
            who = f"{emp}'s job posting, {posted_label(q['posted'] or '')}" if emp else f"Your Craigslist job posting, {posted_label(q['posted'] or '')}"
            leads.append({"token": token, "employer": emp, "quote": q["quote"].strip().rstrip("."), "who": who,
                          "posted_label": posted_label(q["posted"] or ""), "url": q["url"], "title": title})
            rows.append({"company": emp or "(unnamed Craigslist poster)", "posting_url": q["url"], "posting_title": title,
                         "duty_quoted": q["quote"].strip(), "need": q["need"], "tool": tool,
                         "for_page": f"{cfg['site']}/for/{token}/", "source": q["source"], "posted": (q["posted"] or "")[:10]})
            d = ROOT / "drafts" / tool
            d.mkdir(parents=True, exist_ok=True)
            quote = q["quote"].strip().rstrip(".")
            route = ("Reply through the Craigslist posting (the reply address is behind its Reply button)" if q["source"] == "craigslist"
                     else "Find the hiring manager or owner; the posting itself has no email")
            subj = quote if len(quote) <= 70 else quote[:70].rsplit(" ", 1)[0] + "…"
            body = f"""DRAFT — NOT SENT

To: (not found yet) — {route}: {q['url']}
Subject: "{subj}"

Hi,

Your posting for the "{title}" job lists this as part of the work: "{quote}."

I read that line as a step more than a role. So I built the step. Paste in your own {cfg['items']} and it does the work. {cfg['free']}; all of them is $5, once. If you'd want it built around how your team actually works, reply and we'll talk.

Here it is, already done on {cfg['example']}: {cfg['site']}/for/{token}/

Best,
Aidan
"""
            (d / f"{slug(emp or 'craigslist-' + token)}.md").write_text(body)
        (DESK / tool / "leads.json").write_text(json.dumps(leads, indent=1))
        print(tool, len(leads), "leads")
    with (ROOT / "leads.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows ->", ROOT / "leads.csv")


if __name__ == "__main__":
    main()
