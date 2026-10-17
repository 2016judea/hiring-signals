"""Cluster the AI-doable need labels into canonical needs and rank by distinct employers.

Reads data/duties.jsonl, writes data/needs.json (ranked) and data/need_map.json (label ->
canonical need). One `claude -p` call maps every distinct label. An employer is its
normalised name; an unnamed Craigslist poster counts as one employer per posting
(unnamed posters are not merged, so the count can only overstate by reposts, which
Craigslist mostly removes).
"""
import collections, json, re, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = [json.loads(l) for l in (ROOT / "data" / "duties.jsonl").open()]
ai = [r for r in rows if r["ai_doable"] and r.get("need")]
labels = sorted({r["need"].lower().strip() for r in ai})
cache = ROOT / "data" / "need_map.json"

if not cache.exists():
    SYSTEM = ("You group short labels for job duties into canonical needs. Return a mapping for EVERY input label to one "
              "canonical need (a 3-7 word generic phrase naming the underlying work step a software tool could take over). "
              "Merge labels that a single tool would serve (e.g. 'enter invoices into accounting system' and 'process accounts "
              "payable' -> 'process vendor invoices into the books'). Aim for 25-45 canonical needs. Be consistent.")
    schema = {"type": "object", "properties": {"map": {"type": "array", "items": {"type": "object", "properties": {
        "label": {"type": "string"}, "need": {"type": "string"}}, "required": ["label", "need"]}}}, "required": ["map"]}
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "", "--system-prompt", SYSTEM, "--json-schema",
                        json.dumps(schema), "--output-format", "json", "\n".join(labels)],
                       capture_output=True, text=True, timeout=1200)
    m = {x["label"].lower().strip(): x["need"] for x in json.loads(r.stdout)["structured_output"]["map"]}
    cache.write_text(json.dumps(m, indent=1))
m = json.loads(cache.read_text())


def emp_key(r):
    e = (r.get("employer") or "").lower()
    e = re.sub(r"[^a-z0-9 ]", "", e)
    e = re.sub(r"\b(inc|llc|co|corp|company|the|group|services|of)\b", "", e).strip()
    return e or f"anon:{r['id']}"


needs = collections.defaultdict(lambda: {"employers": set(), "postings": set(), "quotes": [], "named": set()})
missing = 0
for r in ai:
    n = m.get(r["need"].lower().strip())
    if not n:
        missing += 1
        continue
    d = needs[n]
    k = emp_key(r)
    d["employers"].add(k)
    if not k.startswith("anon:"):
        d["named"].add(r["employer"])
    d["postings"].add(r["id"])
    d["quotes"].append({"quote": r["quote"], "employer": r.get("employer"), "url": r["url"], "title": r["title"],
                        "source": r["source"], "posted": r.get("posted")})
out = sorted(({"need": n, "employers": len(d["employers"]), "named_employers": sorted(d["named"]),
               "postings": len(d["postings"]), "quotes": d["quotes"]} for n, d in needs.items()),
             key=lambda x: -x["employers"])
(ROOT / "data" / "needs.json").write_text(json.dumps(out, indent=1))
print(f"{len(rows)} duties, {len(ai)} AI-doable, {len(labels)} labels, {len(out)} needs, {missing} unmapped")
for x in out[:30]:
    print(f"{x['employers']:4d} employers {x['postings']:4d} posts  {x['need']}  (named {len(x['named_employers'])})")
