"""Sweep Minneapolis Craigslist job sections and read every posting body.

Writes data/craigslist_postings.jsonl, one posting per line. Re-runs reuse
data/cache/cl/ so a posting is fetched once.
"""
import html, json, re, subprocess, sys, time, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "cl"
CACHE.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
SECTIONS = ["ofc", "acc", "bus", "csr", "mar", "sls", "trp", "rej", "sof", "hum", "lgl",
            "med", "hea", "edu", "egr", "sad", "tch", "web", "npo", "wri", "mnu", "lab",
            "fbh", "ret", "sec", "spa", "trd", "gov", "sci", "tfr", "jjj"]


def get(url):
    key = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".html")
    if key.exists() and key.stat().st_size > 0:
        return key.read_text(errors="ignore")
    r = subprocess.run(["curl", "-sL", "--max-time", "30", "-A", UA, url], capture_output=True, text=True)
    key.write_text(r.stdout)
    time.sleep(0.6)
    return r.stdout


def clean(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("QR Code Link to This Post", "")
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def main():
    seen = {}
    for sec in SECTIONS:
        page = get(f"https://www.craigslist.org/search/area/minneapolis?cat={sec}")
        rows = re.findall(r'<li class="cl-static-search-result" title="([^"]*)">\s*<a href="([^"]+)".*?class="location">\s*([^<]*?)\s*</div>', page, re.S)
        print(sec, len(rows), file=sys.stderr)
        for title, url, loc in rows:
            seen.setdefault(url, {"section": sec, "title": html.unescape(title), "url": url, "location": loc.strip()})
    out = (ROOT / "data" / "craigslist_postings.jsonl").open("w")
    for i, p in enumerate(seen.values()):
        body = get(p["url"])
        m = re.search(r'<section id="postingbody">(.*?)</section>', body, re.S)
        d = re.search(r'<time class="date timeago" datetime="([^"]+)"', body)
        attrs = re.findall(r'<span class="attr[^"]*">(.*?)</span>', body, re.S)
        p["body"] = clean(m.group(1)) if m else ""
        p["posted"] = d.group(1) if d else ""
        p["attrs"] = [clean(a) for a in attrs]
        out.write(json.dumps(p) + "\n")
    print(len(seen), "postings", file=sys.stderr)


if __name__ == "__main__":
    main()
