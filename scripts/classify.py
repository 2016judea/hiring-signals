"""Pull duty lines out of every posting and classify each as AI-doable or not.

Uses `claude -p --model sonnet` on Aidan's subscription ($0). Batches of 8 postings,
6 in parallel, cached per batch in data/cache/classify/. Writes data/duties.jsonl.
"""
import concurrent.futures as cf, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cache" / "classify"
CACHE.mkdir(parents=True, exist_ok=True)

SYSTEM = """You read job postings and pull out the DUTIES: the steps of work the employer is paying a salary for.
For each posting return the employer's name as the posting gives it (null if the posting never names it),
and every duty, quoted VERBATIM from the posting (a short exact substring, one duty each).
Classify each duty:
- ai_doable=true when the step is reasoning over information a tool could take over end to end from inputs the employer already has:
  reading, comparing, qualifying, deciding, drafting, summarising, reconciling, scheduling-from-a-list, data entry from documents,
  writing copy, answering written inquiries, screening resumes, building quotes from specs, coding/categorising records.
- ai_doable=false for physical work, driving, in-person care, live selling/relationships, phone calls that need a human voice,
  supervising people, and anything that needs presence.
For each ai_doable duty give `need`: a short generic noun phrase (3-7 words) naming the underlying step so the same need from
different employers gets the same words, e.g. "screen and rank job applicants", "draft social media posts",
"enter invoices into accounting system", "reconcile bank and credit card statements", "follow up on unpaid invoices",
"write job estimates from customer specs", "answer customer emails", "qualify inbound leads", "schedule appointments from requests",
"process insurance claims and billing codes", "summarise and file documents", "build reports from spreadsheets".
Skip boilerplate (EEO, benefits, qualifications that are not duties)."""

SCHEMA = {
    "type": "object",
    "properties": {"postings": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "employer": {"type": ["string", "null"]},
            "duties": {"type": "array", "items": {"type": "object", "properties": {
                "quote": {"type": "string"}, "ai_doable": {"type": "boolean"},
                "need": {"type": ["string", "null"]}}, "required": ["quote", "ai_doable", "need"]}}},
        "required": ["id", "employer", "duties"]}}},
    "required": ["postings"],
}


def load():
    rows = []
    for name in ("craigslist_postings.jsonl", "ats_postings.jsonl"):
        for line in (ROOT / "data" / name).open():
            p = json.loads(line)
            p.setdefault("source", "craigslist")
            if p.get("section") == "art":   # cat=art is arts & crafts FOR SALE, not jobs
                continue
            if p["source"] == "craigslist" and p.get("posted", "") < "2026-09-02":
                continue
            p["id"] = hashlib.sha1(p["url"].encode()).hexdigest()[:10]
            rows.append(p)
    return rows


def run(batch):
    key = CACHE / (hashlib.sha1("".join(p["id"] for p in batch).encode()).hexdigest() + ".json")
    if key.exists():
        return json.loads(key.read_text())
    prompt = "\n\n".join(f"=== id={p['id']}\nTITLE: {p['title']}\n{p['body'][:5000]}" for p in batch)
    for attempt in range(3):
        r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--system-prompt", SYSTEM,
                            "--json-schema", json.dumps(SCHEMA), "--output-format", "json", prompt],
                           capture_output=True, text=True, timeout=600)
        try:
            out = json.loads(r.stdout).get("structured_output")
            if out and out.get("postings"):
                key.write_text(json.dumps(out))
                return out
        except Exception:
            pass
        print("retry", attempt, r.stdout[:200], file=sys.stderr)
    return {"postings": []}


def main():
    rows = load()
    by = {p["id"]: p for p in rows}
    batches = [rows[i:i + 8] for i in range(0, len(rows), 8)]
    out = (ROOT / "data" / "duties.jsonl").open("w")
    done = 0
    with cf.ThreadPoolExecutor(14) as ex:
        for res in ex.map(run, batches):
            done += 1
            for c in res["postings"]:
                p = by.get(c["id"])
                if not p:
                    continue
                for d in c["duties"]:
                    out.write(json.dumps({"id": p["id"], "source": p["source"], "url": p["url"], "title": p["title"],
                                          "employer": c["employer"] or p.get("employer"), "posted": p.get("posted"),
                                          **d}) + "\n")
            print(f"{done}/{len(batches)}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
