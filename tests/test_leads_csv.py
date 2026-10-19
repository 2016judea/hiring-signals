"""scripts/leads.py rewrites leads.csv on every run. The campaign keeps its state in extra
columns of that same file (status, to, scheduled_for, zoho_message_id, note), so a rerun of the
README pipeline step used to drop them (2026-10-18). write_leads keeps any column it did not
compute, keyed on for_page, and never writes to anything else; this test runs it on a temp file.
"""
import csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from leads import write_leads  # noqa: E402

NEW = [{"company": "Acme", "posting_url": "u1", "posting_title": "t", "duty_quoted": "q", "need": "n", "tool": "x",
        "for_page": "https://x/for/aaaa1111/", "source": "craigslist", "posted": "2026-10-01"},
       {"company": "Beta", "posting_url": "u2", "posting_title": "t", "duty_quoted": "q", "need": "n", "tool": "x",
        "for_page": "https://x/for/bbbb2222/", "source": "lever", "posted": "2026-10-02"}]


def read(p):
    return list(csv.DictReader(p.open()))


def test_a_rerun_keeps_the_campaign_columns(tmp_path):
    p = tmp_path / "leads.csv"
    write_leads(p, NEW)
    assert read(p)[0].keys() == NEW[0].keys()
    rows = read(p)
    rows[0].update(status="sent", to="a@acme.test", zoho_message_id="123", note="first touch")
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    write_leads(p, [{**NEW[0], "posted": "2026-10-03"}, NEW[1]])
    out = read(p)
    assert list(out[0]) == list(NEW[0]) + ["status", "to", "zoho_message_id", "note"]
    assert out[0]["status"] == "sent" and out[0]["to"] == "a@acme.test" and out[0]["posted"] == "2026-10-03"
    assert out[1]["status"] == "" and out[1]["company"] == "Beta"


def test_the_shipped_ledger_columns_survive_a_rerun_of_the_shipped_rows():
    rows = read(ROOT / "leads.csv")
    extra = [c for c in rows[0] if c not in NEW[0]]
    assert extra, "leads.csv carries no campaign columns; nothing to protect"
    assert all(r["for_page"] for r in rows) and len({r["for_page"] for r in rows}) == len(rows)
