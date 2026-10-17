"""Pull public ATS job boards (Greenhouse, Lever, Ashby) and keep Twin Cities postings
from the last ~30 days. Slugs were harvested by web search for boards that list a
Minneapolis/St. Paul posting (2026-10-17). Writes data/ats_postings.jsonl.
"""
import html, json, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GREENHOUSE = ["lpc", "herselfhealth", "sixspeed", "lumbermens", "metrolegalservices", "jamf", "sezzle",
              "branch", "stackline", "pretiumpartnersllc", "apexcompaniescsw", "tegnainc", "merceradvisors",
              "spothopper", "1800gotjunk", "stronghouse", "timeproofusa", "smartsheet", "esri", "vixxo"]
LEVER = ["bold-orange", "court-avenue", "stoneridgesoftware", "fulcrumpro", "brightonjones", "walkerconsultants",
         "stanleygroup", "flynncompanies", "sogoodsoyou", "andersencorp", "Aprio", "kpaonline", "insomniacookies",
         "print-recruiting", "workwave", "jetsetpilates", "kitware", "perforce"]
ASHBY = ["blank-metal", "Swoop", "gravie", "paceloangroup", "barnes", "hoxhunt", "traba", "miter", "fira-health",
         "hims-and-hers", "Flock%20Safety", "directive"]
TC = re.compile(r"minneapolis|st\.? paul|saint paul|twin cities|bloomington, mn|eden prairie|edina|plymouth, mn|"
                r"minnetonka|roseville, mn|eagan|burnsville|maple grove|st\. louis park|golden valley|cottage grove|"
                r"brooklyn park|richfield|woodbury|lakeville|shakopee|\bmn\b|minnesota", re.I)
CUTOFF = datetime.now(timezone.utc) - timedelta(days=45)


def get(url):
    r = subprocess.run(["curl", "-sL", "--max-time", "40", url], capture_output=True, text=True)
    time.sleep(0.3)
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def text(s):
    s = html.unescape(s or "")
    s = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", s)
    s = re.sub(r"<li[^>]*>", "\n- ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", html.unescape(s))).strip()


def main():
    out = []
    for slug in GREENHOUSE:
        d = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true") or {}
        for j in d.get("jobs", []):
            loc = (j.get("location") or {}).get("name", "")
            if not TC.search(loc):
                continue
            upd = j.get("updated_at") or j.get("first_published") or ""
            out.append({"source": "greenhouse", "employer": j.get("company_name") or slug, "board": slug,
                        "title": j["title"], "location": loc, "url": j["absolute_url"], "posted": upd,
                        "body": text(j.get("content"))})
    for slug in LEVER:
        d = get(f"https://api.lever.co/v0/postings/{slug}?mode=json") or []
        if not isinstance(d, list):
            continue
        for j in d:
            loc = (j.get("categories") or {}).get("location", "") or ""
            alls = " ".join((j.get("categories") or {}).get("allLocations", []) or [])
            if not TC.search(loc + " " + alls):
                continue
            posted = datetime.fromtimestamp(j.get("createdAt", 0) / 1000, timezone.utc).isoformat()
            body = text(j.get("description")) + "\n" + "\n".join(
                f"{l.get('text','')}\n{text(l.get('content'))}" for l in j.get("lists", []))
            out.append({"source": "lever", "employer": slug, "board": slug, "title": j["text"], "location": loc,
                        "url": j["hostedUrl"], "posted": posted, "body": body})
    for slug in ASHBY:
        d = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false") or {}
        for j in d.get("jobs", []):
            loc = j.get("location", "") + " " + " ".join(
                (s.get("location") or "") for s in j.get("secondaryLocations", []) or [])
            if not TC.search(loc):
                continue
            out.append({"source": "ashby", "employer": slug.replace("%20", " "), "board": slug, "title": j["title"],
                        "location": loc.strip(), "url": j["jobUrl"], "posted": j.get("publishedAt", ""),
                        "body": j.get("descriptionPlain") or text(j.get("descriptionHtml"))})
    keep = []
    for p in out:
        try:
            dt = datetime.fromisoformat(p["posted"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = None
        if dt is None or dt >= CUTOFF:
            keep.append(p)
    with (ROOT / "data" / "ats_postings.jsonl").open("w") as f:
        for p in keep:
            f.write(json.dumps(p) + "\n")
    print(len(out), "TC postings,", len(keep), "in window", file=sys.stderr)


if __name__ == "__main__":
    main()
