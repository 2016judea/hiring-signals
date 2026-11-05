# Hiring signals

A job posting is a company writing down, in its own words, a step of work it will pay a
salary for. This repo sweeps Twin Cities postings, pulls out the duty lines, classifies
each as a step a tool can take over or not, and ranks the AI-doable needs by how many
distinct employers posted them. A need repeated across employers became a tool.

    python3 scripts/craigslist.py   # Craigslist job sections, bodies cached in data/cache/
    python3 scripts/ats.py          # public Greenhouse / Lever / Ashby boards, TC locations
    python3 scripts/classify.py     # duty lines + AI-doable, via claude -p (sonnet, $0)
    python3 scripts/cluster.py      # canonical needs, ranked by distinct employers -> data/needs.json
    python3 scripts/leads.py        # leads.csv, drafts/<tool>/*.md (DRAFT, NOT SENT), each tool's leads.json

Sweep of 2026-10-17: 1,112 postings, 4,752 duty lines, 928 AI-doable, 46 needs. Merged
into `~/Desktop/workspace/demand-signals/demand.duckdb` by its `load_hiring_signals.py` (table `ask_duty`).

Built from it: paperwork-sorter.vercel.app, estimate-drafter-mn.vercel.app,
report-from-export.vercel.app. `template/` is the shared tool + $5 paywall scaffold they
were copied from.
